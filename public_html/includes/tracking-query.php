<?php
// Preserve attribution across canonical redirects without carrying routing parameters.
function kan_tracking_query() {
    $allowed = ['gclid', 'gbraid', 'wbraid', 'fbclid', 'msclkid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id'];
    $values = [];
    foreach ($allowed as $key) {
        if (isset($_GET[$key]) && is_string($_GET[$key]) && strlen($_GET[$key]) <= 2048) {
            $values[$key] = $_GET[$key];
        }
    }
    return $values ? '?' . http_build_query($values, '', '&', PHP_QUERY_RFC3986) : '';
}
