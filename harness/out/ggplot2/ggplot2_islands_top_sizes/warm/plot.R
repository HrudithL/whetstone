library(ggplot2)
library(readr)
library(dplyr)

islands <- read_csv("islands.csv")

top <- islands %>%
  arrange(desc(size)) %>%
  slice_head(n = 15) %>%
  mutate(name = reorder(name, size))

plot <- ggplot(top, aes(x = name, y = size)) +
  geom_col(fill = "#3A5A40") +
  coord_flip() +
  labs(
    title = "The 15 Largest Landmasses by Area",
    x = NULL,
    y = "Area (thousands of square miles)"
  ) +
  theme_minimal()

ggsave("plot.png", plot, width = 8, height = 5, dpi = 150)
