library(readr)
library(dplyr)
library(ggplot2)

islands <- read_csv("islands.csv", show_col_types = FALSE)

top_islands <- islands |>
  slice_max(size, n = 15) |>
  mutate(name = reorder(name, size))

plot <- ggplot(top_islands, aes(x = size, y = name)) +
  geom_col(fill = "#2C6FB3") +
  geom_text(aes(label = scales::comma(size)),
            hjust = -0.15, size = 3.2, color = "grey30") +
  scale_x_continuous(labels = scales::comma,
                     expand = expansion(mult = c(0, 0.12))) +
  labs(
    title = "The 15 Largest Landmasses by Area",
    subtitle = "Continents and major islands, ranked from biggest to smallest",
    x = "Area (thousands of square miles)",
    y = NULL
  ) +
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold"),
    panel.grid.major.y = element_blank(),
    panel.grid.minor.x = element_blank()
  )

ggsave("plot.png", plot, width = 8, height = 5, dpi = 150)
