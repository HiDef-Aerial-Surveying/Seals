import torch
import pandas as pd
from torchvision import datasets, transforms, models
from torch.autograd import Variable
from utils.dataloaders.data_loader_train_det import ImageFolderTrainDet
from utils.dataloaders.transforms_det import ShapeTransform
import time
import warnings
import argparse
from utils.model_library import *

# image transforms seem to cause truncated images, so we need this
from PIL import ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

warnings.filterwarnings('ignore', module='PIL')

parser = argparse.ArgumentParser(description='validates a CNN at the haul out level')
parser.add_argument('--training_dir', type=str, help='base directory to recursively search for validation images in')
parser.add_argument('--model_architecture', type=str, help='model architecture, must be a member of models '
                                                           'dictionary')
parser.add_argument('--hyperparameter_set', type=str, help='combination of hyperparameters used, must be a member of '
                                                           'hyperparameters dictionary')
parser.add_argument('--model_name', type=str, help='name of input model file from training, this name will also be used'
                                                   'in subsequent steps of the pipeline')
parser.add_argument('--pipeline', type=str, help='name of the detection pipeline where the model is loaded from')
parser.add_argument('--ablation', type=int, default=0, help='boolean for whether or not this validation run will work '
                                                            'on the ablation dataset. runs on regular training sets'
                                                            'by default')
parser.add_argument('--dest_folder', type=str, default='saved_models', help='folder where the model will be saved')

# load arguments
args = parser.parse_args()

# check for invalid inputs
if args.model_architecture not in model_archs:
    raise Exception("Invalid architecture -- see supported architectures:  {}".format(list(model_archs.keys())))

if args.training_dir not in training_sets:
    raise Exception("Training set is not defined in ./utils/model_library.py")

if args.hyperparameter_set not in hyperparameters:
    raise Exception("Hyperparameter combination is not defined in ./utils/model_library.py")

if args.pipeline not in model_defs:
    raise Exception('Pipeline is not defined in ./utils/model_library.py')


def validate_model(model, dest_folder, val_dir, out_file, pipeline, batch_size=2, input_size=299, num_workers=1):
    """
    Generates a confusion matrix from a PyTorch model and validation images

    :param model: pyTorch model (already trained)
    :param val_dir: str -- directory with validation images
    :param batch_size: int -- number of images per batch
    :param input_size: int -- size of input images
    :param to_csv : whether or not pandas dataframe gets saved as a .csv table
    :return: pd.data.frame -- data frame with predictions and labels by validation batch
    """

    # crop and normalize images
    data_transforms = transforms.Compose([
        transforms.CenterCrop(input_size),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    # variant for counting
    shape_transform = ShapeTransform(input_size, train=False)
    int_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    # load dataset
    if args.pipeline == 'Pipeline1':
        dataset = datasets.ImageFolder('./training_sets/{}/validation'.format(val_dir + '_ablation' * args.ablation),
                                       data_transforms)
        class_names = dataset.classes

    else:
        dataset = ImageFolderTrainDet('./training_sets/{}/validation'.format(val_dir + '_ablation' * args.ablation),
                                      shape_transform, int_transform)

    # separate into batches with dataloader
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, num_workers=num_workers)

    # check for GPU support
    use_gpu = torch.cuda.is_available()

    # create pandas data.frame for confusion matrix
    conf_matrix = pd.DataFrame(columns=['predicted', 'ground_truth'])

    # set training flag to False
    model.train(False)

    # keep track of correct answers to get accuracy
    running_corrects = 0

    # keep track of running time
    since = time.time()

    for data in dataloader:

        # get the inputs
        if args.pipeline == "Pipeline1":
            inputs, targets = data

        else:
            inputs, _, targets = data
            targets.type(torch.FloatTensor)

        # gpu support
        if use_gpu:
            inputs = inputs.cuda()
            targets = targets.cuda()

        # do a forward pass to get predictions
        outputs = model(inputs)

        if args.pipeline == "Pipeline1":
            _, preds = torch.max(outputs.data, 1)

            # keep track of correct answers to get accuracy
            running_corrects += torch.sum(preds == targets.data).item()
            conf_matrix_batch = pd.DataFrame(data=[[class_names[int(ele)] for ele in preds],
                                                   [class_names[int(ele)] for ele in targets.data]])

        else:
            conf_matrix_batch = pd.DataFrame(data=[[float(ele) for ele in outputs],
                                                   [float(ele) for ele in targets.data]])

        # add current predictions to conf_matrix
        conf_matrix_batch = conf_matrix_batch.transpose()
        conf_matrix_batch.columns = ['predicted', 'ground_truth']
        conf_matrix = conf_matrix.append(conf_matrix_batch)

    time_elapsed = time.time() - since

    # print output
    print('Validation complete in {}h {:.0f}m {:.0f}s'.format(
        time_elapsed // 3600, time_elapsed // 60, time_elapsed % 60))
    if args.pipeline == "Pipeline1":
        print('Validation Acc: {:4f}'.format(running_corrects / len(dataset)))

    # get total number of tunable parameters
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    # add running time and total number of parameters to conf matrix
    conf_matrix = conf_matrix.append({'ground_truth': (time_elapsed / len(dataset)) * 1000, 'predicted': total_params},
                                     ignore_index=True)

    # save output to .csv for plotting
    conf_matrix.to_csv('./{}/{}/{}/{}_validation.csv'.format(dest_folder, pipeline, out_file, out_file), index=False)


def main():
    # create model instance
    if args.pipeline == 'Pipeline1':
        num_classes = training_sets[args.training_dir]['num_classes']
        model_ft = model_defs[args.pipeline][args.model_architecture](num_classes)

    else:
        model_ft = model_defs[args.pipeline][args.model_architecture]

    # check for GPU support and set model to evaluation mode
    use_gpu = torch.cuda.is_available()
    if use_gpu:
        model_ft.cuda()
    model_ft.eval()

    # load saved model weights from pt_train.py
    model_ft.load_state_dict(torch.load("./{}/{}/{}/{}.tar".format(args.dest_folder, args.pipeline, args.model_name,
                                                                   args.model_name)))

    # run validation to get confusion matrix
    validate_model(model=model_ft, input_size=model_archs[args.model_architecture]['input_size'],
                   pipeline=args.pipeline, batch_size=hyperparameters[args.hyperparameter_set]['batch_size_test'],
                   val_dir=args.training_dir, out_file=args.model_name, dest_folder=args.dest_folder,
                   num_workers=hyperparameters[args.hyperparameter_set]['num_workers_train'])


if __name__ == '__main__':
    main()
