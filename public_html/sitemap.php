<?php
// Five focused sitemaps, served from a reviewed canonical-page registry.
// Read-only: no recursive include and no file writes during a request.
$index = json_decode(file_get_contents(__DIR__ . '/includes/content-index.json'), true);
if (!is_array($index)) { http_response_code(503); exit; }
$part = isset($_GET['bagian']) && is_string($_GET['bagian']) ? $_GET['bagian'] : '';
if ((isset($_GET['bagian']) && !is_string($_GET['bagian'])) || ($part !== '' && !isset($index['groups'][$part]))) {
    http_response_code(404); exit;
}
function kan_xml($value) { return htmlspecialchars((string)$value, ENT_XML1 | ENT_QUOTES, 'UTF-8'); }
function kan_page_modified($entry) {
    $latest = 0;
    foreach ($entry['lastmod_files'] as $relative) {
        $path = __DIR__ . '/' . $relative;
        if (is_file($path)) { $latest = max($latest, filemtime($path)); }
    }
    return $latest;
}
header('Content-Type: application/xml; charset=UTF-8');
header('X-Content-Type-Options: nosniff');
echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
if ($part === '') {
    echo '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
    foreach ($index['groups'] as $name => $entries) {
        $modified = 0;
        foreach ($entries as $entry) { $modified = max($modified, kan_page_modified($entry)); }
        echo '  <sitemap><loc>' . kan_xml($index['domain'] . '/sitemap-' . $name . '.xml') . '</loc>';
        if ($modified) { echo '<lastmod>' . gmdate('Y-m-d\TH:i:s\Z', $modified) . '</lastmod>'; }
        echo '</sitemap>' . "\n";
    }
    echo '</sitemapindex>';
} else {
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">' . "\n";
    foreach ($index['groups'][$part] as $entry) {
        $modified = kan_page_modified($entry);
        echo '  <url><loc>' . kan_xml($index['domain'] . $entry['path']) . '</loc>';
        if ($modified) { echo '<lastmod>' . gmdate('Y-m-d\TH:i:s\Z', $modified) . '</lastmod>'; }
        foreach (($entry['images'] ?? []) as $image) { echo '<image:image><image:loc>' . kan_xml($image) . '</image:loc></image:image>'; }
        echo '</url>' . "\n";
    }
    echo '</urlset>';
}
