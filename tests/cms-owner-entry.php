<?php
declare(strict_types=1);
/* Actual loader function with synthetic private bootstrap files only. */
require __DIR__ . '/../cms/owner-entry.php';
use KanCms\{GatewayConfig, TrustedOwner, Storage, Denied};
$repo = realpath(__DIR__ . '/..');
$base = sys_get_temp_dir() . '/kan-owner-entry-' . bin2hex(random_bytes(12));
mkdir($base, 0700);
foreach (['store','domain-one','domain-two','declared-repo','private'] as $name) mkdir($base . '/' . $name, 0700);
$baseline = json_decode(file_get_contents($repo . '/public_html/includes/refresh-data.json'), true, 32, JSON_THROW_ON_ERROR);
$_SERVER['DOCUMENT_ROOT'] = $base . '/domain-one';
$GLOBALS['bindingConfig'] = new GatewayConfig($base . '/store',
    [$base . '/domain-one', $base . '/domain-two'], [$base . '/declared-repo'],
    $baseline, 'synthetic-owner', str_repeat('a',40),
    ['a'=>'produk-39db8e80530c','b'=>'produk-fcf95321686c']);
$GLOBALS['bindingOwner'] = new TrustedOwner('synthetic-owner', time()+3600);
$code = '<?php return ["config"=>$GLOBALS["bindingConfig"],"owner"=>$GLOBALS["bindingOwner"]];';
$results = [];
function testEntry(string $name, callable $fn): void {
    global $results;
    try { $fn(); $results[]=['name'=>$name,'status'=>'PASS']; }
    catch (Throwable $error) { $results[]=['name'=>$name,'status'=>'FAIL','category'=>get_class($error)]; }
}
function rejectedEntry(string $category): void {
    try { KanCms\ownerBinding(); }
    catch (Throwable $error) { if ($error instanceof $category) return; throw $error; }
    throw new LogicException('Expected denial');
}
function bindingFile(string $path, int $mode=0600): void {
    global $code;
    file_put_contents($path,$code); chmod($path,$mode); putenv('CMS_OWNER_BOOTSTRAP='.$path);
}
try {
    testEntry('actual-loader-missing-binding-denied',function(){putenv('CMS_OWNER_BOOTSTRAP');rejectedEntry(Storage::class);});
    testEntry('actual-loader-private-binding-accepted',function() use($base){bindingFile($base.'/private/binding.php');$r=KanCms\ownerBinding();if($r['owner']->identity!=='synthetic-owner')throw new LogicException('Binding');});
    testEntry('actual-loader-non-owner-denied',function(){ $GLOBALS['bindingOwner']=new TrustedOwner('synthetic-other',time()+3600);rejectedEntry(Denied::class);$GLOBALS['bindingOwner']=new TrustedOwner('synthetic-owner',time()+3600);});
    testEntry('actual-loader-expired-owner-denied',function(){ $GLOBALS['bindingOwner']=new TrustedOwner('synthetic-owner',time());rejectedEntry(Denied::class);$GLOBALS['bindingOwner']=new TrustedOwner('synthetic-owner',time()+3600);});
    testEntry('actual-loader-second-document-root-denied',function() use($base){bindingFile($base.'/domain-two/binding.php');rejectedEntry(Storage::class);});
    testEntry('actual-loader-declared-repository-denied',function() use($base){bindingFile($base.'/declared-repo/binding.php');rejectedEntry(Storage::class);});
    testEntry('actual-loader-readable-by-others-denied',function() use($base){bindingFile($base.'/private/open.php',0644);rejectedEntry(Storage::class);});
    testEntry('actual-loader-symlink-denied',function() use($base){symlink($base.'/private/binding.php',$base.'/private/link.php');putenv('CMS_OWNER_BOOTSTRAP='.$base.'/private/link.php');rejectedEntry(Storage::class);});
} finally {
    putenv('CMS_OWNER_BOOTSTRAP');
    foreach (['store','domain-one','domain-two','declared-repo','private'] as $name) {
        foreach (new DirectoryIterator($base.'/'.$name) as $file) if(!$file->isDot())unlink($file->getPathname());
        rmdir($base.'/'.$name);
    }
    rmdir($base);
}
$failed=count(array_filter($results,fn($r)=>$r['status']!=='PASS'));
echo json_encode(['passed'=>count($results)-$failed,'failed'=>$failed,'results'=>$results],JSON_THROW_ON_ERROR|JSON_PRETTY_PRINT)."\n";
exit($failed?1:0);
