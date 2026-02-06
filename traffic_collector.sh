#!/bin/bash
#export PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
export PATH="/opt/homebrew/opt/mariadb@10.5/bin:/opt/homebrew/opt/php@8.3/sbin:/opt/homebrew/opt/php@8.3/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/System/Cryptexes/App/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/local/bin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/bin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/appleinternal/bin"
cd /Users/geodesiundip/Documents/Micro-mobility/traffic-data
Rscript traffic_collector.R
 
