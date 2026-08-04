library(ggplot2)
library(readr)

cars <- read_csv("gtcars.csv")

plot <- ggplot(cars, aes(x = hp, y = msrp, color = ctry_origin)) +
  geom_point(size = 3, alpha = 0.85) +
  scale_y_continuous(labels = scales::label_dollar(scale = 1e-3, suffix = "K")) +
  scale_x_continuous(labels = scales::label_comma()) +
  scale_color_brewer(palette = "Set2") +
  labs(
    title = "Price Climbs with Horsepower Across Sports Cars",
    subtitle = "Manufacturer's suggested retail price vs. engine horsepower",
    x = "Horsepower (hp)",
    y = "MSRP (USD)",
    color = "Country of origin"
  ) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "right")

ggsave("plot.png", plot, width = 8, height = 5, dpi = 150)
