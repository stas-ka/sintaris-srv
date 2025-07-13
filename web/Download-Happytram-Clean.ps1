$SitemapPath = "happytram_sitemap.xml"
$DownloadDir = "happytram_full_site"
$AssetDir = "$DownloadDir\assets"

# Создание директорий
New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
New-Item -ItemType Directory -Path $AssetDir -Force | Out-Null

# Чтение ссылок из sitemap
[xml]$sitemap = Get-Content $SitemapPath
$urls = $sitemap.urlset.url.loc

foreach ($url in $urls) {
    try {
        $uri = [Uri]$url
        $filename = ($uri.AbsolutePath.TrimEnd("/") -replace "[^\w]", "_") + ".html"
        $filepath = Join-Path $DownloadDir $filename

        Invoke-WebRequest -Uri $url -OutFile $filepath -UseBasicParsing
        Write-Host "Страница скачана: $url → $filename"
    } catch {
        Write-Warning "Не удалось скачать $url"
    }
}

# Шаблон ресурсов TildaCDN
$pattern = 'https://static\.tildacdn\.com/[\w\-/]+\.(png|jpg|jpeg|gif|svg|webp|css|js|woff2?)'

# Обработка всех HTML-файлов
Get-ChildItem $DownloadDir -Filter *.html | ForEach-Object {
    $htmlPath = $_.FullName
    $content = Get-Content $htmlPath -Raw
    $original = $content
    $matches = [regex]::Matches($content, $pattern)

    foreach ($match in $matches) {
        $url = $match.Value
        $filename = Split-Path $url -Leaf
        $localPath = Join-Path $AssetDir $filename

        if (-not (Test-Path $localPath)) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $localPath -UseBasicParsing
                Write-Host "Скачан: $filename"
            } catch {
                Write-Warning "Ошибка при скачивании: $url"
            }
        }

        # Замена ссылок
        $escaped = [Regex]::Escape($url)
        $content = $content -replace $escaped, "assets/$filename"
    }

    if ($content -ne $original) {
        Set-Content -Path $htmlPath -Value $content -Encoding UTF8
        Write-Host "Файл обновлён: $htmlPath"
    }
}

Write-Host ""
Write-Host "Готово. Все файлы сохранены в папке $DownloadDir"
