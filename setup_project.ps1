# setup_project.ps1
# Run from: C:\Users\james\Projects\DataScience\Repositories\survivor-fantasy
# Creates all directories and placeholder files for the survivor-fantasy project.
# Safe to run repeatedly — uses -Force on New-Item to avoid errors on existing paths.

param(
    [string]$Root = $PSScriptRoot
)

Set-Location $Root
Write-Host "`nsurvivor-fantasy project scaffold" -ForegroundColor Cyan
Write-Host "Root: $Root`n" -ForegroundColor Gray

# ── Helper ────────────────────────────────────────────────────────────────────

function New-Dir {
    param([string]$Path)
    $full = Join-Path $Root $Path
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
        Write-Host "  [DIR]  $Path" -ForegroundColor Green
    }
}

function New-File {
    param([string]$Path, [string]$Content = "")
    $full = Join-Path $Root $Path
    if (-not (Test-Path $full)) {
        New-Item -ItemType File -Path $full -Force | Out-Null
        if ($Content) { Set-Content -Path $full -Value $Content -Encoding UTF8 }
        Write-Host "  [FILE] $Path" -ForegroundColor Yellow
    } else {
        Write-Host "  [SKIP] $Path (already exists)" -ForegroundColor DarkGray
    }
}

# ── Directories ───────────────────────────────────────────────────────────────

Write-Host "Creating directories..." -ForegroundColor Cyan

# Data — all gitignored, documented rebuild in README
New-Dir "data"
New-Dir "data\survivoR_exports"
New-Dir "data\season50"
New-Dir "data\features"

# Python package
New-Dir "src"
New-Dir "src\survivor_fantasy"
New-Dir "src\survivor_fantasy\db"
New-Dir "src\survivor_fantasy\pipeline"
New-Dir "src\survivor_fantasy\models"
New-Dir "src\survivor_fantasy\nlp"
New-Dir "src\survivor_fantasy\schemas"
New-Dir "src\survivor_fantasy\viz"

# Frontend
New-Dir "frontend"
New-Dir "frontend\css"
New-Dir "frontend\js"
New-Dir "frontend\data"

# Other
New-Dir "notebooks"
New-Dir "tests"
New-Dir "notes"
New-Dir "docs"

# ── Python Package Init Files ─────────────────────────────────────────────────

Write-Host "`nCreating Python package files..." -ForegroundColor Cyan

$init_comment = "# This file makes the directory a Python package."

New-File "src\survivor_fantasy\__init__.py"           $init_comment
New-File "src\survivor_fantasy\db\__init__.py"        $init_comment
New-File "src\survivor_fantasy\pipeline\__init__.py"  $init_comment
New-File "src\survivor_fantasy\models\__init__.py"    $init_comment
New-File "src\survivor_fantasy\nlp\__init__.py"       $init_comment
New-File "src\survivor_fantasy\schemas\__init__.py"   $init_comment
New-File "src\survivor_fantasy\viz\__init__.py"       $init_comment
New-File "tests\__init__.py"                          $init_comment

# ── Source Module Stubs ───────────────────────────────────────────────────────

Write-Host "`nCreating source module stubs..." -ForegroundColor Cyan

New-File "src\survivor_fantasy\db\connect.py"
New-File "src\survivor_fantasy\db\schema.py"

New-File "src\survivor_fantasy\pipeline\ingest.py"
New-File "src\survivor_fantasy\pipeline\ingest_s50.py"
New-File "src\survivor_fantasy\pipeline\features.py"
New-File "src\survivor_fantasy\pipeline\scorer.py"
New-File "src\survivor_fantasy\pipeline\publish.py"

New-File "src\survivor_fantasy\models\survival.py"
New-File "src\survivor_fantasy\models\network.py"
New-File "src\survivor_fantasy\models\bayesian.py"
New-File "src\survivor_fantasy\models\challenges.py"
New-File "src\survivor_fantasy\models\optimizer.py"

New-File "src\survivor_fantasy\nlp\confessionals.py"
New-File "src\survivor_fantasy\nlp\edit_classifier.py"

New-File "src\survivor_fantasy\schemas\episode_output.py"
New-File "src\survivor_fantasy\schemas\events_input.py"

New-File "src\survivor_fantasy\viz\survival_plots.py"
New-File "src\survivor_fantasy\viz\network_plots.py"
New-File "src\survivor_fantasy\viz\posterior_plots.py"

# ── Test Stubs ────────────────────────────────────────────────────────────────

Write-Host "`nCreating test stubs..." -ForegroundColor Cyan

New-File "tests\test_schema.py"
New-File "tests\test_ingest.py"
New-File "tests\test_features.py"
New-File "tests\test_scorer.py"

# ── Notebooks ─────────────────────────────────────────────────────────────────

Write-Host "`nCreating notebook stubs..." -ForegroundColor Cyan

$nb_template = '{"cells":[],"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","version":"3.11.0"}},"nbformat":4,"nbformat_minor":5}'

New-File "notebooks\01_data_exploration.ipynb"    $nb_template
New-File "notebooks\02_survival_analysis.ipynb"   $nb_template
New-File "notebooks\03_network_analysis.ipynb"    $nb_template
New-File "notebooks\04_bayesian_model.ipynb"      $nb_template
New-File "notebooks\05_nlp_experiments.ipynb"     $nb_template

# ── Frontend ──────────────────────────────────────────────────────────────────

Write-Host "`nCreating frontend stubs..." -ForegroundColor Cyan

New-File "frontend\index.html"
New-File "frontend\scorecard.html"
New-File "frontend\css\styles.css"
New-File "frontend\js\leaderboard.js"
New-File "frontend\js\scorecard.js"

# ── Data Placeholders ─────────────────────────────────────────────────────────

Write-Host "`nCreating data placeholders..." -ForegroundColor Cyan

# .gitkeep files keep gitignored directories tracked in the repo
New-File "data\survivoR_exports\.gitkeep"  "# Add survivoR CSV exports here. See docs/data_dictionary.md."
New-File "data\features\.gitkeep"          "# Generated by `make build`. Do not edit manually."

# events.csv — header only, ready for S50 manual entry
$events_header = "season,episode,player_name,still_in_game,tribe_name,merge_status,attended_tc,voted_out,votes_received,had_individual_immunity,tribe_won_immunity,tribe_immunity_place,reward_participant,won_individual_reward,found_idol_clue,found_hidden_idol,played_idol,played_idol_for,voted_out_holding_idol,lost_vote,quit,medevac,received_jury_vote,sole_survivor,confessional_count"
New-File "data\season50\events.csv"   $events_header

# rosters.csv — header only
$rosters_header = "league_player,survivor_player,is_active,draft_order"
New-File "data\season50\rosters.csv"  $rosters_header

# ── Documentation ─────────────────────────────────────────────────────────────

Write-Host "`nCreating documentation stubs..." -ForegroundColor Cyan

New-File "docs\schema.md"
New-File "docs\data_dictionary.md"
New-File "docs\modeling.md"

# ── Notes ─────────────────────────────────────────────────────────────────────

Write-Host "`nCreating notes stubs..." -ForegroundColor Cyan

New-File "notes\methods_explainer.md"
New-File "notes\project_plan.md"
# on_strategy_and_bias.md should already exist if copied from Claude output

# ── Top-Level Files ───────────────────────────────────────────────────────────

Write-Host "`nCreating top-level config files..." -ForegroundColor Cyan

New-File "pyproject.toml"
New-File "config.yaml"
New-File "Makefile"
New-File ".gitignore"
New-File "README.md"

# ── R Export Script ───────────────────────────────────────────────────────────

Write-Host "`nCreating R export script..." -ForegroundColor Cyan

$r_script = @'
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
'@

New-File "scripts\export_survivoR.R" $r_script

# ── Summary ───────────────────────────────────────────────────────────────────

Write-Host "`n── Scaffold complete ──────────────────────────────────" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Copy content files from Claude outputs into this scaffold" -ForegroundColor Gray
Write-Host "     (README.md, config.yaml, pyproject.toml, Makefile," -ForegroundColor Gray
Write-Host "      .gitignore, schema.py, connect.py, all schema/*.py," -ForegroundColor Gray
Write-Host "      docs/, notes/on_strategy_and_bias.md)" -ForegroundColor Gray
Write-Host "  2. pip install -e .[dev]" -ForegroundColor Gray
Write-Host "  3. Open R and run: source('scripts/export_survivoR.R')" -ForegroundColor Gray
Write-Host "  4. make ingest" -ForegroundColor Gray
Write-Host ""
