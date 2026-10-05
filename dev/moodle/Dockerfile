FROM php:8.3-apache
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev libicu-dev libzip-dev libpng-dev libjpeg62-turbo-dev libfreetype6-dev libxml2-dev libonig-dev git unzip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j2 pgsql pdo_pgsql intl zip gd soap exif opcache mbstring \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer
WORKDIR /var/www/moodle
COPY moodle/composer.json moodle/composer.lock ./
RUN composer install --no-interaction --prefer-dist --no-progress
RUN sed -i 's/Listen 80/Listen 127.0.0.1:8088/' /etc/apache2/ports.conf \
    && sed -i 's/<VirtualHost \*:80>/<VirtualHost 127.0.0.1:8088>/;s@/var/www/html@/var/www/moodle/public@' /etc/apache2/sites-available/000-default.conf \
    && printf '<Directory /var/www/moodle/public>\nAllowOverride All\nRequire all granted\n</Directory>\n' > /etc/apache2/conf-available/moodle.conf \
    && a2enconf moodle && a2enmod rewrite \
    && printf 'max_input_vars=5000\nmemory_limit=512M\nupload_max_filesize=32M\npost_max_size=32M\n' > /usr/local/etc/php/conf.d/moodle.ini
RUN apt-get update && apt-get install -y --no-install-recommends locales \
    && sed -i 's/# en_AU.UTF-8 UTF-8/en_AU.UTF-8 UTF-8/;s/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen && rm -rf /var/lib/apt/lists/*
