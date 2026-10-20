Add-Type -AssemblyName System.Drawing
$outDir = Join-Path $PSScriptRoot '..\custom_components\monoprice\brand'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
foreach ($size in @(256,512)) {
  $bitmap = [Drawing.Bitmap]::new($size,$size)
  $graphics = [Drawing.Graphics]::FromImage($bitmap)
  $graphics.Clear([Drawing.Color]::FromArgb(15,110,160))
  $font = [Drawing.Font]::new('Arial',($size * 0.34),[Drawing.FontStyle]::Bold,[Drawing.GraphicsUnit]::Pixel)
  $format = [Drawing.StringFormat]::new()
  $format.Alignment = [Drawing.StringAlignment]::Center
  $format.LineAlignment = [Drawing.StringAlignment]::Center
  $graphics.DrawString('AV',$font,[Drawing.Brushes]::White,[Drawing.RectangleF]::new(0,0,$size,$size),$format)
  $name = if ($size -eq 256) {'icon.png'} else {'icon@2x.png'}
  $bitmap.Save((Join-Path $outDir $name),[Drawing.Imaging.ImageFormat]::Png)
  $graphics.Dispose(); $bitmap.Dispose(); $font.Dispose(); $format.Dispose()
}
