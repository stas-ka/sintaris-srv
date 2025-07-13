# === Настройки ===
$SitemapPath = "happytram_sitemap.xml"
$OutputDir = "happytram_full_site"
$AssetDir = Join-Path $OutputDir "assets"

# === Создание директорий ===
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $AssetDir | Out-Null

# === Загрузка URL из Sitemap ===
[xml]$sitemap = Get-Content $SitemapPath
$urls = $sitemap.urlset.url.loc

# === Загружаем HTML-файлы и сохраняем ===
foreach ($url in $urls) {
    $uri = [Uri]$url
    $slug = ($uri.AbsolutePath -replace '[^\w\-]', '_').Trim('_')
    if ($slug -eq "") { $slug = "index" }
    $fileName = "${slug}.html"
    $filePath = Join-Path $OutputDir $fileName

    try {
        Invoke-WebRequest -Uri $url -OutFile $filePath -UseBasicParsing
        Write-Host "HTML downloaded: $url"
    } catch {
        Write-Warning "Error by: $url"
    }
}

# === Обработка HTML: Скачивание ресурсов и замена ссылок ===
$pattern = 'https://static\.tildacdn\.com/[\w\-\/]+\.(png|jpg|jpeg|gif|svg|webp|woff2?|ttf|css|js)'

Get-ChildItem -Path $OutputDir -Filter *.html | ForEach-Object {
    $file = $_.FullName
    $content = Get-Content $file -Raw

    # Добавляем meta charset, если отсутствует
    if ($content -notmatch '<meta\s+charset\s*=\s*["' + "'" + ']utf-8["' + "'" + ']') {
        $content = $content -replace '<head>', '<head>`n<meta charset="utf-8">'
    }

    $matches = [regex]::Matches($content, $pattern)
    foreach ($match in $matches) {
        $url = $match.Value
        $filename = Split-Path $url -Leaf
        $localPath = Join-Path $AssetDir $filename

        if (-not (Test-Path $localPath)) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $localPath -UseBasicParsing
                Write-Host "СPcitured downloaded: $filename"
            } catch {
                Write-Warning "Не удалось скачать: $url"
            }
        }

        $escapedUrl = [regex]::Escape($url)
        $content = $content -replace $escapedUrl, "assets/$filename"
    }

    # Сохраняем с правильной кодировкой
    #[System.IO.File]::WriteAllText($file, $content, [System.Text.Encoding]::UTF8)
    Write-Host "File is Done: $file"
}

Write-Host "All files done."
