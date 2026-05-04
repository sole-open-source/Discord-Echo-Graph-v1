#!/bin/bash
set -e

exec supervisord -c /etc/supervisord.conf
