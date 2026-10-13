<?php
declare(strict_types=1);
/* Read source tokens without executing public API/configuration. No literals are reported. */
if (PHP_VERSION_ID < 80300 || PHP_VERSION_ID >= 80400) { fwrite(STDERR, "PHP83 runtime required\n"); exit(1); }
$root = realpath($argv[1] ?? '');
if (!$root || !is_dir($root . '/public_html')) { fwrite(STDERR, "Invalid source root\n"); exit(1); }
$files = glob($root . '/public_html/*.php') ?: [];
foreach (glob($root . '/public_html/includes/*.php') ?: [] as $file) $files[] = $file;
$files[] = $root . '/cms/neon_box_pilot.php';
sort($files);
$skip = [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT];
$removed = ['each','create_function','get_magic_quotes_gpc','get_magic_quotes_runtime','set_magic_quotes_runtime',
 'money_format','hebrevc','convert_cyr_string','restore_include_path','__autoload','ereg','eregi','ereg_replace',
 'eregi_replace','split','spliti','sql_regcase','mysql_connect','mysql_query','mysql_fetch_assoc','mysql_num_rows',
 'mysql_real_escape_string','mysql_select_db','mysql_close'];
$deprecated = ['utf8_encode','utf8_decode','strftime','gmstrftime','date_sunrise','date_sunset'];
$functions = []; $parsed = []; $issues = [];
function meaningful(array $tokens, int $index, int $step): mixed {
    global $skip;
    while (isset($tokens[$index])) {
        $token = $tokens[$index];
        if (!is_array($token) || !in_array($token[0], $skip, true)) return $token;
        $index += $step;
    }
    return null;
}
foreach ($files as $file) {
    $relative = substr($file, strlen($root) + 1);
    if (!is_file($file) || is_link($file)) { $issues[] = ['path'=>$relative,'category'=>'unsafe source']; continue; }
    try { $tokens = token_get_all(file_get_contents($file), TOKEN_PARSE); }
    catch (Throwable $error) { $issues[] = ['path'=>$relative,'category'=>'PHP83 parse failure']; continue; }
    foreach ($tokens as $index=>$token) {
        if (is_array($token) && $token[0] === T_FUNCTION) {
            $next = meaningful($tokens, $index+1, 1);
            if ($next === '&') $next = meaningful($tokens, $index+2, 1);
            if (is_array($next) && $next[0] === T_STRING) $functions[strtolower($next[1])] = true;
        }
    }
    $parsed[$relative] = $tokens;
}
$inventory = [];
foreach ($parsed as $relative=>$tokens) {
    $calls=[]; $extensions=[]; $unknown=[]; $runtime=[]; $includes=0; $dynamicCalls=0;
    foreach ($tokens as $index=>$token) {
        if (!is_array($token)) continue;
        if (in_array($token[0], [T_INCLUDE,T_INCLUDE_ONCE,T_REQUIRE,T_REQUIRE_ONCE], true)) $includes++;
        if ($token[0] === T_VARIABLE && meaningful($tokens,$index+1,1) === '(') $dynamicCalls++;
        if (!in_array($token[0], [T_STRING,T_NAME_FULLY_QUALIFIED,T_NAME_QUALIFIED], true)
            || meaningful($tokens,$index+1,1) !== '(') continue;
        $prev = meaningful($tokens,$index-1,-1);
        if (is_array($prev) && in_array($prev[0], [T_FUNCTION,T_NEW,T_OBJECT_OPERATOR,T_NULLSAFE_OBJECT_OPERATOR,T_DOUBLE_COLON], true)) continue;
        $name = strtolower(ltrim($token[1], '\\'));
        $calls[$name] = true;
        if (in_array($name,$removed,true)) $issues[]=['path'=>$relative,'category'=>'removed function','function'=>$name];
        if (in_array($name,$deprecated,true)) $issues[]=['path'=>$relative,'category'=>'deprecated function requires review','function'=>$name];
        if (function_exists($name)) {
            $reflection = new ReflectionFunction($name);
            if ($reflection->isInternal()) $extensions[$reflection->getExtensionName() ?: 'Core'] = true;
        } elseif (!isset($functions[$name])) {
            $unknown[$name] = true;
        }
        foreach (['curl_'=>'curl/network','mysqli_'=>'database','pdo_'=>'database','mail'=>'mail',
            'session_'=>'session','file_put_contents'=>'filesystem write','fopen'=>'filesystem access',
            'rename'=>'filesystem write','unlink'=>'filesystem write','mkdir'=>'filesystem write'] as $prefix=>$category) {
            if ($name === $prefix || str_starts_with($name,$prefix)) $runtime[$category]=true;
        }
    }
    ksort($calls); ksort($extensions); ksort($unknown); ksort($runtime);
    $inventory[]=['path'=>$relative,'call_count'=>count($calls),'extensions'=>array_keys($extensions),
        'unresolved_function_names'=>array_keys($unknown),'include_count'=>$includes,
        'dynamic_call_count'=>$dynamicCalls,'runtime_dependencies'=>array_keys($runtime)];
}
$loaded=get_loaded_extensions(); sort($loaded);
echo json_encode(['php_version'=>PHP_VERSION,'php_sapi'=>PHP_SAPI,'files'=>$inventory,
    'loaded_extensions'=>$loaded,'issues'=>$issues,
    'limits'=>['Tokens identify direct functions only; dynamic calls, methods, configuration values and live integrations are not executed.',
    'Public API/configuration source is parsed without reporting string literals or invoking it.']], JSON_THROW_ON_ERROR|JSON_PRETTY_PRINT) . "\n";
exit($issues ? 1 : 0);
