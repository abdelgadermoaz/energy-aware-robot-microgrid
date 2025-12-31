param(
  [Parameter(Mandatory=$false)]
  [string]$RunDir = "outputs/latest",

  [Parameter(Mandatory=$false)]
  [string]$Prefix = "peak_mission"
)

# Ensure destination exists
New-Item -ItemType Directory -Force -Path "docs/figures" | Out-Null

# If RunDir is outputs/latest but that's not a real folder, tell the user
if (-not (Test-Path $RunDir)) {
  Write-Host "Run directory not found: $RunDir" -ForegroundColor Red
  Write-Host "Tip: use a timestamp folder like outputs/20251231_201617" -ForegroundColor Yellow
  exit 1
}

# Map source -> destination
$files = @(
  @{ src = "fig_price_robot_kw.png";   dst = "${Prefix}_price_robot_kw.png" },
  @{ src = "fig_cumulative_cost.png";  dst = "${Prefix}_cumulative_cost.png" },
  @{ src = "fig_grid_kw.png";          dst = "${Prefix}_grid_kw.png" },
  @{ src = "fig_soc.png";              dst = "${Prefix}_soc.png" }
)

foreach ($f in $files) {
  $srcPath = Join-Path $RunDir $f.src
  $dstPath = Join-Path "docs/figures" $f.dst

  if (-not (Test-Path $srcPath)) {
    Write-Host "Missing: $srcPath" -ForegroundColor Red
    exit 1
  }

  Copy-Item $srcPath $dstPath -Force
  Write-Host "Copied: $srcPath -> $dstPath"
}

Write-Host "Done. Figures updated in docs/figures/" -ForegroundColor Green
