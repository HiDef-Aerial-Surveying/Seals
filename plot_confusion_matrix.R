library(ggplot2)
library(reshape2)
library(scales)

# plot confusion matrix
get_confusion_matrix = function(csv_file, labels){
    rows = read.csv(csv_file, stringsAsFactors=FALSE)
    n_labels = length(labels)
    conf_matrix = data.frame(matrix(0, nrow=n_labels, ncol=n_labels), row.names=labels)
    colnames(conf_matrix) = labels
    for(row in 1:dim(rows)[1]){
        conf_matrix[rows[row, "ground_truth"], rows[row, "predicted"]] = conf_matrix[rows[row, "ground_truth"], rows[row, "predicted"]] + 1
    }
    plot_df = melt(as.matrix(conf_matrix))
    print(plot_df)
    plot = ggplot(plot_df, aes(Var1, Var2)) + # x and y axes => Var1 and Var2
        geom_tile(aes(fill = value)) + # background colours are mapped according to the value column
        geom_text(aes(fill = plot_df$value, label = round(plot_df$value, 2))) + # write the values
        scale_fill_gradient2(low = muted("darkred"), 
                             mid = "white", 
                             high = muted("midnightblue"), 
                             midpoint = mean(plot_df$value)) + # determine the colour
        theme(panel.grid.major.x=element_blank(), #no gridlines
              panel.grid.minor.x=element_blank(), 
              panel.grid.major.y=element_blank(), 
              panel.grid.minor.y=element_blank(),
              panel.background=element_rect(fill="white"), # background=white
              axis.text.x = element_text(angle=90, hjust = 1,vjust=1,size = 12,face = "bold"),
              plot.title = element_text(size=20,face="bold"),
              axis.text.y = element_text(size = 12,face = "bold")) + 
        ggtitle("Confusion Matrix") + 
        theme(legend.title=element_text(face="bold", size=14)) + 
        scale_x_discrete(name="") +
        scale_y_discrete(name="") 
    
    print(plot)
    return(conf_matrix)
    
}

labels = c('crabeater', 'weddell', 'pack-ice', 'other', 'emperor')

ae = get_confusion_matrix(csv_file='29_3_2018_16_30_conf_matrix.csv', labels=labels)

