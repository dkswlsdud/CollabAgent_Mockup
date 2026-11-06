FROM nginx:stable-alpine

COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY static/ /usr/share/nginx/html/static/

EXPOSE 80
