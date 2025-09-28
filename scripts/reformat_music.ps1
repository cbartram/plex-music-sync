# Plex Music Organizer Script
# This script organizes MP3 files into Plex-compatible folder structure
# Usage: Update the $sourceDir and $targetDir variables below, then run the script

# Configuration
$sourceDir = "C:\Users\cbart\OneDrive\Desktop\songs"
$targetDir = "C:\Users\cbart\OneDrive\Desktop\songs_organized"
$dryRun = $false  # Set to $false to actually move files

# Create target directory if it doesn't exist
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force
    Write-Host "Created target directory: $targetDir" -ForegroundColor Green
}

# Function to sanitize folder/file names (remove invalid characters)
function Sanitize-Name {
    param($name)
    $invalidChars = [IO.Path]::GetInvalidFileNameChars() -join ''
    $name = $name -replace "[$([regex]::Escape($invalidChars))]", ""
    $name = $name.Trim()
    if ([string]::IsNullOrWhiteSpace($name)) {
        return "Unknown"
    }
    return $name
}

# Function to get metadata from MP3 file
function Get-Mp3Metadata {
    param($filePath)
    
    try {
        $shell = New-Object -ComObject Shell.Application
        $folder = $shell.Namespace((Get-Item $filePath).DirectoryName)
        $file = $folder.ParseName((Get-Item $filePath).Name)
        
        # Common metadata property indices
        $artist = $folder.GetDetailsOf($file, 13)      # Contributing artists
        $album = $folder.GetDetailsOf($file, 14)       # Album
        $title = $folder.GetDetailsOf($file, 21)       # Title
        $trackNumber = $folder.GetDetailsOf($file, 26) # Track number
        $albumArtist = $folder.GetDetailsOf($file, 204) # Album artist
        
        # Clean up the metadata
        $artist = if ($artist) { $artist.Trim() } else { "" }
        $album = if ($album) { $album.Trim() } else { "" }
        $title = if ($title) { $title.Trim() } else { "" }
        $trackNumber = if ($trackNumber) { $trackNumber.Trim() } else { "" }
        $albumArtist = if ($albumArtist) { $albumArtist.Trim() } else { "" }
        
        return @{
            Artist = $artist
            Album = $album
            Title = $title
            TrackNumber = $trackNumber
            AlbumArtist = $albumArtist
        }
    }
    catch {
        Write-Warning "Could not read metadata for $filePath : $($_.Exception.Message)"
        return $null
    }
}

# Function to format track number
function Format-TrackNumber {
    param($trackNum)
    if ([string]::IsNullOrWhiteSpace($trackNum)) {
        return "00"
    }
    
    # Extract just the number part (handle formats like "1/12" or "01")
    if ($trackNum -match '(\d+)') {
        $num = [int]$matches[1]
        return $num.ToString("00")
    }
    return "00"
}

# Get all MP3 files
$mp3Files = Get-ChildItem -Path $sourceDir -Filter "*.mp3" -File

Write-Host "Found $($mp3Files.Count) MP3 files to process" -ForegroundColor Cyan
Write-Host "DRY RUN MODE: $dryRun (no files will be moved)" -ForegroundColor Yellow
Write-Host ""

$processedCount = 0
$errorCount = 0

foreach ($file in $mp3Files) {
    Write-Host "Processing: $($file.Name)" -ForegroundColor White
    
    $metadata = Get-Mp3Metadata -filePath $file.FullName
    
    if ($null -eq $metadata) {
        Write-Host "  ERROR: Could not read metadata" -ForegroundColor Red
        $errorCount++
        continue
    }
    
    # Determine artist (prefer AlbumArtist, fallback to Artist)
    $artistName = if ($metadata.AlbumArtist) { $metadata.AlbumArtist } else { $metadata.Artist }
    
    # Handle multiple artists or empty artist
    if ([string]::IsNullOrWhiteSpace($artistName)) {
        # Try to extract from filename
        if ($file.BaseName -match '^(.+?)\s*-\s*(.+)$') {
            $artistName = $matches[1].Trim()
        } else {
            $artistName = "Unknown Artist"
        }
    }
    
    # Handle multiple artists (contains comma, semicolon, or " feat ")
    if ($artistName -match '[,;]|\sfeat\s|\sft\s|\s&\s') {
        # For compilations/multiple artists, you might want to use "Various Artists"
        # Or use the first artist. Let's use the first artist for now.
        $artistName = ($artistName -split '[,;&]')[0].Trim()
        $artistName = ($artistName -split '\sfeat\s|\sft\s')[0].Trim()
    }
    
    # Set album name
    $albumName = if ($metadata.Album) { $metadata.Album } else { "Unknown Album" }
    
    # Set track title
    $trackTitle = if ($metadata.Title) { $metadata.Title } else {
        # Try to extract from filename
        if ($file.BaseName -match '^.+?\s*-\s*(.+)$') {
            $matches[1].Trim()
        } else {
            $file.BaseName
        }
    }
    
    # Format track number
    $trackNum = Format-TrackNumber -trackNum $metadata.TrackNumber
    
    # Sanitize all names
    $artistName = Sanitize-Name -name $artistName
    $albumName = Sanitize-Name -name $albumName
    $trackTitle = Sanitize-Name -name $trackTitle
    
    # Create target path
    $artistDir = Join-Path $targetDir $artistName
    $albumDir = Join-Path $artistDir $albumName
    $newFileName = "$trackNum - $trackTitle.mp3"
    $targetPath = Join-Path $albumDir $newFileName
    
    Write-Host "  Artist: $artistName" -ForegroundColor Gray
    Write-Host "  Album: $albumName" -ForegroundColor Gray
    Write-Host "  Track: $trackNum - $trackTitle" -ForegroundColor Gray
    Write-Host "  Target: $targetPath" -ForegroundColor Gray
    
    if (-not $dryRun) {
        try {
            # Create directories if they don't exist
            if (-not (Test-Path $albumDir)) {
                New-Item -ItemType Directory -Path $albumDir -Force | Out-Null
            }
            
            # Check if target file already exists
            if (Test-Path $targetPath) {
                Write-Host "  WARNING: Target file already exists, skipping" -ForegroundColor Yellow
            } else {
                # Move the file
                Move-Item -Path $file.FullName -Destination $targetPath
                Write-Host "  MOVED successfully" -ForegroundColor Green
                $processedCount++
            }
        }
        catch {
            Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
            $errorCount++
        }
    } else {
        Write-Host "  DRY RUN: Would move to $targetPath" -ForegroundColor Cyan
        $processedCount++
    }
    
    Write-Host ""
}

# Summary
Write-Host "=== SUMMARY ===" -ForegroundColor Yellow
Write-Host "Files processed: $processedCount" -ForegroundColor Green
if ($errorCount -gt 0) {
    Write-Host "Errors encountered: $errorCount" -ForegroundColor Red
}

if ($dryRun) {
    Write-Host ""
    Write-Host "This was a DRY RUN - no files were actually moved." -ForegroundColor Yellow
    Write-Host "To actually move the files, set `$dryRun = `$false at the top of the script." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Files have been organized for Plex!" -ForegroundColor Green
    Write-Host "You can now add '$targetDir' as a Music library in Plex." -ForegroundColor Green
}