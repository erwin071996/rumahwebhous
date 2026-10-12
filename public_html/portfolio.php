<?php
header('Content-Type: application/json');

$baseDir = 'foto-produk';
$allowedExt = ['jpg','jpeg','png','webp'];

$result = [];

function scanFolder($dir, $baseDir, &$result, $allowedExt) {
    foreach (scandir($dir) as $item) {
        if ($item === '.' || $item === '..') continue;

        $path = $dir . '/' . $item;

        if (is_dir($path)) {
            scanFolder($path, $baseDir, $result, $allowedExt);
        } else {
            $ext = strtolower(pathinfo($item, PATHINFO_EXTENSION));
            if (in_array($ext, $allowedExt)) {
                $result[] = str_replace($baseDir . '/', '', $path);
            }
        }
    }
}

scanFolder($baseDir, $baseDir, $result, $allowedExt);

echo json_encode($result);
