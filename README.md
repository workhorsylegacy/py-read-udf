py-read-udf2
==========

A module for reading DVD ISOs (Universal Disk Format) with Python 2 &amp; 3

Currently it can only list the files at the root of a disk.


Example use:
-----
~~~python

import read_udf
game_file = 'C:/games/Playstation2/Armored Core 3/Armored Core 3.iso'
root_directory = read_udf.read_udf_file(game_file)
for entry in root_directory.all_entries:
	print("file name: {0}".format(entry.file_identifier))

~~~


Much of the code was ported from the C# DiscUtils project:
https://discutils.codeplex.com


See ECMA-167 and OSTA Universal Disk Format for details:

http://en.wikipedia.org/wiki/Universal_Disk_Format
https://sites.google.com/site/udfintro/
http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
http://www.osta.org/specs/pdf/udf260.pdf


