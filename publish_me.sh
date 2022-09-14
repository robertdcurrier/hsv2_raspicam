#!/bin/bash
echo "Setting serial to default of hsv0000"
echo "update configuration set value = 'hsv0000' where setting = 'serial'" | sqlite3 config.db 
echo "Setting version to current date/time..."
date=`date -I`
echo "update configuration set value = '$date' where setting = 'version'" | sqlite3 config.db 
echo "Copying hsv2_raspicam.py and config.db to ~/habscope"
cp -p hsv2_raspicam.py ~/habscope
cp -p config.db ~/habscope
cp -p habscope.png ~/habscope
cp -p run.sh ~/habscope
echo "Pushing hsv2_raspicam.py and config.db to habscope2.gcoos.org"
sshpass -p "habsc0p3" scp -p hsv2_raspicam.py  pi@habscope2.gcoos.org:/data/habscope2/updates/habscope_dist/hsv2_raspicam.py
sshpass -p "habsc0p3" scp -p config.db pi@habscope2.gcoos.org:/data/habscope2/updates/habscope_dist/config.db
echo "Done!"
