# deploy.ps1
# Moves downloaded project files from Downloads to their correct destinations.
# Run from project root:
#   .\deploy.ps1
#
# Or run from anywhere with the project path:
#   .\deploy.ps1 -ProjectRoot "C:\Users\james\Projects\DataScience\Repositories\survivor-fantasy"

param(
    [string]$ProjectRoot = "C:\Users\james\Projects\DataScience\Repositories\survivor-fantasy",
    [string]$Downloads   = "C:\Users\james\Downloads"
)

# ── Routing table ─────────────────────────────────────────────────────────────
# Each entry: filename pattern -> destination relative to ProjectRoot
$routes = @(
    # Pipeline scripts
    @{ pattern = "ingest_s50.py";   dest = "src\survivor_fantasy\pipeline\ingest_s50.py" },
    @{ pattern = "scorer.py";       dest = "src\survivor_fantasy\pipeline\scorer.py" },
    @{ pattern = "publish.py";      dest = "src\survivor_fantasy\pipeline\publish.py" },
    @{ pattern = "ingest.py";       dest = "src\survivor_fantasy\pipeline\ingest.py" },
    @{ pattern = "features.py";     dest = "src\survivor_fantasy\pipeline\features.py" },

    # Scripts
    @{ pattern = "scrape_rosters.py"; dest = "scripts\scrape_rosters.py" },
    @{ pattern = "fix_rosters.py";    dest = "scripts\fix_rosters.py" },
    @{ pattern = "fix_nicknames.py";  dest = "scripts\fix_nicknames.py" },
    @{ pattern = "check_db.py";       dest = "scripts\check_db.py" },
    @{ pattern = "deploy.ps1";        dest = "deploy.ps1" },

    # DB / schema
    @{ pattern = "schema.py";       dest = "src\survivor_fantasy\db\schema.py" },
    @{ pattern = "connect.py";      dest = "src\survivor_fantasy\db\connect.py" },
    @{ pattern = "metadata.py";     dest = "src\survivor_fantasy\db\metadata.py" },

    # Schemas
    @{ pattern = "events_input.py";   dest = "src\survivor_fantasy\schemas\events_input.py" },
    @{ pattern = "episode_output.py"; dest = "src\survivor_fantasy\schemas\episode_output.py" },

    # Frontend
    @{ pattern = "buffs.html";      dest = "frontend\buffs.html" },
    @{ pattern = "fjv.html";        dest = "frontend\fjv.html" },
    @{ pattern = "index.html";      dest = "frontend\index.html" },

    # Data
    @{ pattern = "rosters.csv";     dest = "data\season50\rosters.csv" },
    @{ pattern = "events*.csv";     dest = "data\season50\events.csv" },

    # Docs / notes
    @{ pattern = "project_plan.md"; dest = "notes\project_plan.md" },
    @{ pattern = "data_dictionary.md"; dest = "docs\data_dictionary.md" },
    @{ pattern = "schema.md";       dest = "docs\schema.md" },
    @{ pattern = "modeling.md";     dest = "docs\modeling.md" }
)

# ── Run ───────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "deploy.ps1 — routing Downloads to project" -ForegroundColor Cyan
Write-Host "  Project: $ProjectRoot" -ForegroundColor DarkGray
Write-Host "  Source:  $Downloads" -ForegroundColor DarkGray
Write-Host ""

$moved   = 0
$skipped = 0
$unknown = 0

# Get all files in Downloads (non-recursive, top level only)
$files = Get-ChildItem -Path $Downloads -File

foreach ($file in $files) {
    $matched = $false
    foreach ($route in $routes) {
        if ($file.Name -like $route.pattern) {
            $destination = Join-Path $ProjectRoot $route.dest
            $destDir = Split-Path $destination -Parent

            # Create destination directory if it doesn't exist
            if (-not (Test-Path $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }

            # Move (overwrite)
            Move-Item -Path $file.FullName -Destination $destination -Force
            Write-Host "  [OK] $($file.Name)" -ForegroundColor Green -NoNewline
            Write-Host "  ->  $($route.dest)" -ForegroundColor DarkGray
            $moved++
            $matched = $true
            break
        }
    }
    if (-not $matched) {
        # Only flag .py, .html, .md, .csv, .ps1 files as unknown — ignore everything else
        $ext = $file.Extension.ToLower()
        if ($ext -in @('.py', '.html', '.md', '.csv', '.ps1', '.json')) {
            Write-Host "  [??] $($file.Name) — no route defined" -ForegroundColor Yellow
            $unknown++
        } else {
            $skipped++
        }
    }
}

Write-Host ""
Write-Host "  Done: $moved moved, $unknown unrecognized, $skipped non-project files ignored" -ForegroundColor Cyan
Write-Host ""
