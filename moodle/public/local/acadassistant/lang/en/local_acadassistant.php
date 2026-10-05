<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Academic assistant';
$string['ragurl'] = 'RAG service URL';
$string['ragurl_desc'] = 'Base URL for the server-to-server RAG service. Use HTTPS except for loopback development addresses.';
$string['ragsharedsecret'] = 'RAG signing secret';
$string['ragsharedsecret_desc'] = 'Shared HMAC secret used only by the Moodle server to sign short-lived requests. Configure the same value in the RAG service. Use at least 32 characters.';
$string['ragnotconfigured'] = 'The RAG service is not configured.';
$string['ragrequestfailed'] = 'The RAG service could not complete the request.';
