
$RootDir = "happytram_full_pages"
$AssetDir = "$RootDir\assets"
New-Item -ItemType Directory -Force -Path $AssetDir | Out-Null


$FileTypes = "*.html", "*.css", "*.js"


$pattern = 'https://static\.tildacdn\.com/[\w\-/]+\.(png|jpg|jpeg|gif|svg|webp|css|js|woff2?)'


foreach ($ext in $FileTypes) {
    Get-ChildItem -Path $RootDir -Recurse -Include $ext | ForEach-Object {
        $file = $_.FullName
        $content = Get-Content $file -Raw
        $originalContent = $content
        $matches = Select-String -InputObject $content -Pattern $pattern -AllMatches

        foreach ($match in $matches.Matches) {
            $url = $match.Value
            $filename = Split-Path $url -Leaf
            $localPath = Join-Path $AssetDir $filename

            if (-not (Test-Path $localPath)) {
                try {
                    Invoke-WebRequest -Uri $url -OutFile $localPath -UseBasicParsing
                    Write-Host "Скачано: $filename"
                } catch {
                    Write-Warning "Не удалось скачать: $url"
                }
            }


            $escapedUrl = [Regex]::Escape($url)
            $content = $content -replace $escapedUrl, "assets/$filename"
        }


        if ($content -ne $originalContent) {
            Copy-Item $file "$file.bak" -Force
            Set-Content $file $content -Encoding UTF8
            Write-Host "Обновлён: $file"
        }
    }
}

Write-Host ""
Write-Host ""
