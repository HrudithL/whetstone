library(ggplot2)
library(readr)

gtcars <- read_csv("gtcars.csv")

plot <- ggplot(gtcars, aes(x = hp, y = msrp, color = ctry_origin)) +
  geom_point(size = 4.5, alpha = 0.6) +
  scale_color_brewer(palette = "Accent") +
  scale_y_continuous(labels = scales::comma) +
  labs(
    title = "Price vs. Horsepower for Sports Cars",
    x = "Horsepower (hp)",
    y = "Price (MSRP)",
    color = "Country of origin"
  ) +
  theme_minimal() +
  theme(legend.position = "bottom")

ggsave("plot.png", plot, width = 8, height = 5, dpi = 150)
