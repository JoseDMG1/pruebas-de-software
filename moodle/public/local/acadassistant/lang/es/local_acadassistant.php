<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Asistente académico';
$string['ragurl'] = 'URL del servicio RAG';
$string['ragurl_desc'] = 'URL base del servicio RAG para comunicación servidor a servidor. Use HTTPS, excepto para direcciones locales de desarrollo.';
$string['ragsharedsecret'] = 'Secreto de firma del RAG';
$string['ragsharedsecret_desc'] = 'Secreto HMAC compartido que solo usa el servidor Moodle para firmar solicitudes de corta duración. Configure el mismo valor en el servicio RAG. Use al menos 32 caracteres.';
$string['ragnotconfigured'] = 'El servicio RAG no está configurado.';
$string['ragrequestfailed'] = 'El servicio RAG no pudo completar la solicitud.';
