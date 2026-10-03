<?php
$cfg['Servers'][1] = [
    'host' => 'localhost',
    'socket' => '/run/mysqld/mysqld.sock',
    'auth_type' => 'cookie',
    'AllowNoPassword' => false,
    'AllowRoot' => false,
    'only_db' => ['handspeak'],
    'verbose' => 'HandSpeak database',
];
$cfg['ServerDefault'] = 1;
$cfg['AllowArbitraryServer'] = false;
$cfg['LoginCookieValidity'] = 1800;
$cfg['LoginCookieRecall'] = false;
$cfg['LoginCookieStore'] = 0;
$cfg['CookieSameSite'] = 'Strict';
$cfg['TempDir'] = '/var/lib/phpmyadmin/tmp';
