# export_survivoR.R
# One-time script to export survivoR package data to CSV.
# Run this in R before running `make ingest`.
#
# Requirements:
#   install.packages("survivoR")
#   install.packages("readr")

library(survivoR)
library(readr)

out_dir <- "data/survivoR_exports"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

cat("Exporting survivoR datasets...\n")

write_csv(survivoR::seasons,          file.path(out_dir, "seasons.csv"))
write_csv(survivoR::castaways,        file.path(out_dir, "castaways.csv"))
write_csv(survivoR::tribe_colours,    file.path(out_dir, "tribes.csv"))
write_csv(survivoR::vote_history,     file.path(out_dir, "vote_history.csv"))
write_csv(survivoR::challenges,       file.path(out_dir, "challenges.csv"))
write_csv(survivoR::advantage_details,file.path(out_dir, "advantage_details.csv"))
write_csv(survivoR::confessionals,    file.path(out_dir, "confessionals.csv"))
write_csv(survivoR::boot_order,       file.path(out_dir, "boot_order.csv"))

cat("Done. Files written to", out_dir, "\n")
cat("Now run: make ingest\n")
