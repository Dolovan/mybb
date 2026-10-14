<?php
/**
 * Offline reproduction of MyBB's captcha.php renderer.
 *
 * captcha.php needs a database row (imagehash) and the whole MyBB bootstrap.
 * This script copies its drawing code verbatim so that we can render any
 * string we want, as many times as we want, without a running forum. It is
 * used to build the training set / template bank for the solver and to
 * evaluate it.
 *
 * Usage:
 *   php generate.php --out DIR --count N            random 5-char captchas, labels in DIR/labels.txt
 *   php generate.php --out DIR --text ABC12          one captcha with a given string
 *   php generate.php --seed 42 ...                   reproducible noise/fonts (the text itself uses random_int)
 */

$opts = getopt('', ['out:', 'count:', 'text:', 'seed:']);
if(!isset($opts['out']))
{
	fwrite(STDERR, "--out DIR is required\n");
	exit(1);
}
$out = rtrim($opts['out'], '/');
if(!is_dir($out) && !mkdir($out, 0777, true))
{
	fwrite(STDERR, "cannot create {$out}\n");
	exit(1);
}
if(isset($opts['seed']))
{
	mt_srand((int)$opts['seed']);
}

// --- Same constants as captcha.php ---------------------------------------
$img_width = 200;
$img_height = 60;
$min_size = 20;
$max_size = 32;
$min_angle = -30;
$max_angle = 30;

// Fonts: MyBB's inc/captcha_fonts when run inside the repository, otherwise a
// local fonts/ directory (for a standalone copy of this folder).
$ttf_fonts = [];
foreach([__DIR__.'/../inc/captcha_fonts', __DIR__.'/fonts'] as $dir)
{
	foreach(glob($dir.'/*.ttf') as $file)
	{
		$ttf_fonts[] = realpath($file);
	}
	if(count($ttf_fonts) > 0)
	{
		break;
	}
}
if(count($ttf_fonts) == 0 || !function_exists('imagefttext'))
{
	fwrite(STDERR, "FreeType fonts not available; captcha.php would fall back to the bitmap font\n");
	exit(1);
}
$use_ttf = 1;

// --- Render --------------------------------------------------------------
$count = isset($opts['count']) ? (int)$opts['count'] : 1;
$labels = fopen($out.'/labels.txt', 'a');
for($k = 0; $k < $count; ++$k)
{
	$imagestring = isset($opts['text']) ? $opts['text'] : random_str(5);
	$im = render_captcha($imagestring);
	$name = sprintf('%06d_%s.png', $k, $imagestring);
	imagepng($im, $out.'/'.$name);
	imagedestroy($im);
	fwrite($labels, "{$name}\t{$imagestring}\n");
}
fclose($labels);
echo "wrote {$count} captchas to {$out}\n";

// --- Copied from inc/functions.php ---------------------------------------
function random_str($length = 8)
{
	$set = array_merge(range(0, 9), range('A', 'Z'), range('a', 'z'));
	$str = [];
	for($i = 0; $i < $length; ++$i)
	{
		$str[] = $set[random_int(0, 61)];
	}
	shuffle($str);
	return implode($str);
}

// --- Copied from captcha.php (main flow) ---------------------------------
function render_captcha($imagestring)
{
	global $img_width, $img_height;

	$im = imagecreatetruecolor($img_width, $img_height);
	$bg_color = imagecolorallocate($im, 255, 255, 255);
	imagefill($im, 0, 0, $bg_color);

	$to_draw = rand(0, 2);
	if($to_draw == 1)
	{
		draw_circles($im);
	}
	else if($to_draw == 2)
	{
		draw_squares($im);
	}
	else
	{
		draw_lines($im);
	}

	draw_dots($im);
	draw_string($im, $imagestring);

	$border_color = imagecolorallocate($im, 0, 0, 0);
	imagerectangle($im, 0, 0, $img_width - 1, $img_height - 1, $border_color);
	return $im;
}

// --- Copied verbatim from captcha.php ------------------------------------
function draw_lines(&$im)
{
	global $img_width, $img_height;

	for($i = 10; $i < $img_width; $i += 10)
	{
		$color = imagecolorallocate($im, rand(150, 255), rand(150, 255), rand(150, 255));
		imageline($im, $i, 0, $i, $img_height, $color);
	}
	for($i = 10; $i < $img_height; $i += 10)
	{
		$color = imagecolorallocate($im, rand(150, 255), rand(150, 255), rand(150, 255));
		imageline($im, 0, $i, $img_width, $i, $color);
	}
}

function draw_circles(&$im)
{
	global $img_width, $img_height;

	$circles = $img_width * $img_height / 100;
	for($i = 0; $i <= $circles; ++$i)
	{
		$color = imagecolorallocate($im, rand(180, 255), rand(180, 255), rand(180, 255));
		$pos_x = rand(1, $img_width);
		$pos_y = rand(1, $img_height);
		$circ_width = ceil(rand(1, $img_width) / 2);
		$circ_height = rand(1, $img_height);
		imagearc($im, $pos_x, $pos_y, $circ_width, $circ_height, 0, rand(200, 360), $color);
	}
}

function draw_dots(&$im)
{
	global $img_width, $img_height;

	$dot_count = $img_width * $img_height / 5;
	for($i = 0; $i <= $dot_count; ++$i)
	{
		$color = imagecolorallocate($im, rand(200, 255), rand(200, 255), rand(200, 255));
		imagesetpixel($im, rand(0, $img_width), rand(0, $img_height), $color);
	}
}

function draw_squares(&$im)
{
	global $img_width, $img_height;

	$square_count = 30;
	for($i = 0; $i <= $square_count; ++$i)
	{
		$color = imagecolorallocate($im, rand(150, 255), rand(150, 255), rand(150, 255));
		$pos_x = rand(1, $img_width);
		$pos_y = rand(1, $img_height);
		$sq_width = $sq_height = rand(10, 20);
		$pos_x2 = $pos_x + $sq_height;
		$pos_y2 = $pos_y + $sq_width;
		imagefilledrectangle($im, $pos_x, $pos_y, $pos_x2, $pos_y2, $color);
	}
}

function draw_string(&$im, $string)
{
	global $use_ttf, $min_size, $max_size, $min_angle, $max_angle, $ttf_fonts, $img_height, $img_width;

	if(empty($string))
	{
		return false;
	}

	$spacing = $img_width / strlen($string);
	$string_length = strlen($string);
	for($i = 0; $i < $string_length; ++$i)
	{
		$font_size = rand($min_size, $max_size);
		$font = array_rand($ttf_fonts);
		$font = $ttf_fonts[$font];
		$rotation = rand($min_angle, $max_angle);

		$r = rand(0, 200);
		$g = rand(0, 200);
		$b = rand(0, 200);
		$color = imagecolorallocate($im, $r, $g, $b);

		$dimensions = imageftbbox($font_size, $rotation, $font, $string[$i], array());
		$string_width = $dimensions[2] - $dimensions[0];
		$string_height = $dimensions[3] - $dimensions[5];

		$pos_x = $spacing / 4 + $i * $spacing;
		$pos_y = ceil(($img_height - $string_height / 2));

		$shadow_x = rand(-3, 3) + $pos_x;
		$shadow_y = rand(-3, 3) + $pos_y;
		$shadow_color = imagecolorallocate($im, $r + 20, $g + 20, $b + 20);
		imagefttext($im, $font_size, $rotation, (int)$shadow_x, (int)$shadow_y, $shadow_color, $font, $string[$i], array());

		imagefttext($im, $font_size, $rotation, (int)$pos_x, (int)$pos_y, $color, $font, $string[$i], array());
	}
	return true;
}
