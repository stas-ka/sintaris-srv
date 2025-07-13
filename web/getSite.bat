wget --mirror \
     --convert-links \
     --adjust-extension \
     --page-requisites \
     --no-parent \
     --directory-prefix=happytram_full_site \
     --trust-server-names \
     --domains=happytram.com,static.tildacdn.com \
     https://happytram.com/sitemap.xml