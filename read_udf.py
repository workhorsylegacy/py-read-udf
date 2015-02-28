#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Copyright (c) 2015, Matthew Brennan Jones <matthew.brennan.jones@gmail.com>
# A module for reading DVD ISOs (Universal Disk Format) with Python 2 & 3
# See Universal Disk Format (ISO/IEC 13346 and ECMA-167) for details
# http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
# http://www.osta.org/specs/pdf/udf260.pdf
# http://en.wikipedia.org/wiki/Universal_Disk_Format
# See Universal Disk Format (ISO/IEC 13346 and ECMA-167) for details
# It uses a MIT style license
# It is hosted at: https://github.com/workhorsy/py-read-udf2
# 
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import sys, os

HEADER_SIZE = 1024 * 32
SECTOR_SIZE = 1024 * 2 # FIXME: This should not be hard coded

def to_uint8(byte):
	import struct
	return struct.unpack('B', byte)[0]

def to_uint16(buffer, offset):
	left = ((to_uint8(buffer[offset + 1]) << 8) & 0xFF00)
	right = ((to_uint8(buffer[offset + 0]) << 0) & 0x00FF)
	return (left | right)

def to_uint32(buffer, offset):
	a = ((to_uint8(buffer[offset + 3]) << 24) & 0xFF000000)
	b = ((to_uint8(buffer[offset + 2]) << 16) & 0x00FF0000)
	c = ((to_uint8(buffer[offset + 1]) << 8) & 0x0000FF00)
	d = ((to_uint8(buffer[offset + 0]) << 0) & 0x000000FF)
	return(a | b | c | d)




# page 3/4 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class TagIdentifier(object): # enum
	unknown = 0
	PrimaryVolumeDescriptor = 1
	AnchorVolumeDescriptorPointer = 2
	VolumeDescriptorPointer = 3
	ImplementationUseVolumeDescriptor = 4
	PartitionDescriptor = 5
	LogicalVolumeDescriptor = 6
	UnallocatedSpaceDescriptor = 7
	TerminatingDescriptor = 8
	LogicalVolumeIntegrityDescriptor = 9


# page 3/3 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
# page 20 of http://www.osta.org/specs/pdf/udf260.pdf
class DescriptorTag(object):
	def __init__(self, buffer):
		self._is_valid = True
		
		if len(buffer) < 16:
			self._is_valid = False
			return
		
		if to_uint16(buffer, 0) == 0:
			self._is_valid = False

		self.tag_identifier = to_uint16(buffer, 0)
		self.descriptor_version = to_uint16(buffer, 2)
		self.tag_check_sum = to_uint8(buffer[4])
		self.reserved = to_uint8(buffer[5])
		self.tag_serial_number = to_uint16(buffer, 6)
		self.descriptor_crc = to_uint16(buffer, 8)
		self.descriptor_crc_length = to_uint16(buffer, 10)
		self.tag_location = to_uint32(buffer, 12)

		# Make sure the checksum matches
		check_sum = 0
		for i in range(16):
			if i == 4:
				continue
			check_sum += to_uint8(buffer[i])

		# Truncate int to uint8
		while check_sum > 256:
			check_sum -= 256

		if not check_sum == self.tag_check_sum:
			self._is_valid = False
			return

		# Make sure the reserve is zeros
		if not self.reserved == 0:
			self._is_valid = False
			return

	def get_is_valid(self):
		return self._is_valid
	is_valid = property(get_is_valid)


# page 3/15 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class AnchorVolumeDescriptorPointer(object):
	def __init__(self, buffer):
		self._is_valid = True
		
		if len(buffer) < 512:
			self._is_valid = False
			return

		self.descriptor_tag = DescriptorTag(buffer)
		self.main_volume_descriptor_sequence_extent = buffer[16 : 24] # FIXME: extent
		self.reserve_volume_descriptor_sequence_extent = buffer[24 : 32] # FIXME: extent
		self.reserved = buffer[32 : 512]

		# Make sure it is the correct type of tag
		if not self.descriptor_tag.tag_identifier == TagIdentifier.AnchorVolumeDescriptorPointer:
			self._is_valid = False
			return

		# Make sure the reserved space is all zeros
		for n in self.reserved:
			if not to_uint8(n) == 0:
				self._is_valid = False
				return

	def get_is_valid(self):
		return self._is_valid
	is_valid = property(get_is_valid)


# page 3/12 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class PrimaryVolumeDescriptor(object):
	def __init__(self, buffer):
		self._is_valid = True

		if len(buffer) < 512:
			self._is_valid = False
			return

		self.descriptor_tag = DescriptorTag(buffer)
		self.volume_descriptor_sequence_number = uint32(buffer, 16)
		self.primary_volume_descriptor_number = uint32(buffer, 20)
		self.volume_identifier = buffer[24 : 56] # FIXME: d string
		self.volume_sequence_number = to_uint16(buffer, 56)
		self.maximum_volume_sequence_number = to_uint16(buffer, 58)
		self.interchange_level = to_uint16(buffer, 60)
		self.maximum_interchange_level = to_uint16(buffer, 62)
		self.character_set_list = to_uint32(buffer, 64)
		self.maximum_character_set_list = to_uint32(buffer, 68)
		self.volume_set_identifier = buffer[72 : 200] # FIXME: d string
		self.descriptor_character_set = buffer[200 : 264] # FIXME: char spec
		self.expalnatory_character_set = buffer[264 : 328] # FIXME: char spec
		self.volume_abstract = buffer[328 : 336] # FIXME: extent
		self.volume_copyright_notice = buffer[336 : 344] # FIXME: extent
		self.application_identifier = buffer[344 : 376] # FIXME: regid
		self.recording_date_and_time = buffer[376 : 388] # timestamp
		self.implementation_identifier = buffer[388 : 420] # regid
		self.implementation_use = buffer[420 : 484]
		self.predecessor_volume_descriptor_sequence_location = to_uint32(buffer, 484)
		self.flags = to_uint16(buffer, 488)
		self.reserved = buffer[490 : 512]

		# Make sure it is the correct type of tag
		if not self.descriptor_tag.tag_identifier == TagIdentifier.PrimaryVolumeDescriptor:
			self._is_valid = False
			return

		# Make sure the reserved space is all zeros
		for n in self.reserved:
			if not to_uint8(n) == 0:
				self._is_valid = False
				return

	def get_is_valid(self):
		return self._is_valid
	is_valid = property(get_is_valid)


def is_valid_udf(file, file_size):
	# Move to the start of the file
	file.seek(0)

	# Make sure there is enough space for a header and sector
	if file_size < HEADER_SIZE + SECTOR_SIZE:
		return False

	# Move past 32K of empty space
	file.seek(HEADER_SIZE)

	is_valid_descriptor = True
	has_found_marker = False

	# Look at each sector
	while(is_valid_descriptor):
		# Read the next sector
		buffer = file.read(SECTOR_SIZE)
		if len(buffer) < SECTOR_SIZE:
			break

		# Get the sector meta data
		structure_type = to_uint8(buffer[0])
		standard_identifier = buffer[1 : 6]
		structure_version = to_uint8(buffer[6])
		#structure_data = buffer[7 : 2048]
		
		'''
		print(structure_type)
		print(standard_identifier)
		print(structure_version)
		#print(structure_data)
		'''

		if standard_identifier in ['NSR02', 'NSR03']:
			has_found_marker = True
		elif standard_identifier in ['BEA01', 'BOOT2', 'CD001', 'CDW02', 'TEA01']:
			pass
		else:
			is_valid_descriptor = False

	return has_found_marker

def get_sector_size(file, file_size):
	sizes = [4096, 2048, 1024, 512]
	for size in sizes:
		# Skip this size if the file is too small for all the sectors
		if file_size < 257 * size:
			continue

		# Move to the last sector
		file.seek(256 * size)

		# Read the Descriptor Tag
		buffer = file.read(16)
		tag = DescriptorTag(buffer)

		# Skip if the tag is not valid
		if not tag.is_valid:
			continue

		# Skip if the tag thinks it is at the wrong sector
		if not tag.tag_location == 256:
			continue

		# Skip if the sector is not an Anchor Volume Description Pointer
		if not tag.tag_identifier == TagIdentifier.AnchorVolumeDescriptorPointer:
			continue

		# Got the correct size
		return size

	return 0

def go(file, file_size, sector_size):
	if file_size < 257 * sector_size:
		return

	for sector in [256]:#range(257):
		# Move to the last logical sector
		file.seek(sector * sector_size)

		# Read the Descriptor Tag
		buffer = file.read(512)
		tag = DescriptorTag(buffer)
		print('file.tell()', file.tell())

		# Skip if not valid
		if not tag.is_valid:
			continue
		
		print('tag.tag_identifier', tag.tag_identifier)

		if tag.tag_identifier == TagIdentifier.PrimaryVolumeDescriptor:
			print(sector, 'PrimaryVolumeDescriptor')
			print('tag.tag_identifier', tag.tag_identifier)
			print('tag.descriptor_version', tag.descriptor_version)
			print('tag.tag_check_sum', tag.tag_check_sum)
			print('tag.reserved', tag.reserved)
			print('tag.tag_serial_number', tag.tag_serial_number)
			print('tag.descriptor_crc', tag.descriptor_crc)
			print('tag.descriptor_crc_length', tag.descriptor_crc_length)
			print('tag.tag_location', tag.tag_location)
			PrimaryVolumeDescriptor(file.read(512))
		elif tag.tag_identifier == TagIdentifier.AnchorVolumeDescriptorPointer:
			print(sector, 'AnchorVolumeDescriptorPointer')
			anchor = AnchorVolumeDescriptorPointer(file.read(512))
		elif tag.tag_identifier == TagIdentifier.VolumeDescriptorPointer:
			print(sector, 'VolumeDescriptorPointer')
			pass #VolumeDescriptorPointer(file.read(512))
		elif tag.tag_identifier == TagIdentifier.ImplementationUseVolumeDescriptor:
			print(sector, 'ImplementationUseVolumeDescriptor')
			pass #ImplementationUseVolumeDescriptor(file.read(512))
		elif tag.tag_identifier == TagIdentifier.PartitionDescriptor:
			print(sector, 'PartitionDescriptor')
			pass #PartitionDescriptor(file.read(512))
		elif tag.tag_identifier == TagIdentifier.LogicalVolumeDescriptor:
			print(sector, 'LogicalVolumeDescriptor')
			pass #LogicalVolumeDescriptor(file.read(512))
		elif tag.tag_identifier == TagIdentifier.UnallocatedSpaceDescriptor:
			print(sector, 'UnallocatedSpaceDescriptor')
			pass #UnallocatedSpaceDescriptor(file.read(512))
		elif tag.tag_identifier == TagIdentifier.TerminatingDescriptor:
			print(sector, 'TerminatingDescriptor')
			pass #TerminatingDescriptor(file.read(512))
		elif tag.tag_identifier == TagIdentifier.LogicalVolumeIntegrityDescriptor:
			print(sector, 'LogicalVolumeIntegrityDescriptor')
			pass #LogicalVolumeIntegrityDescriptor(file.read(512))
		elif tag.tag_identifier != 0:
			print("Unexpected Descriptor Tag :{0}".format(tag.tag_identifier))
			
		print('file.tell()', file.tell())
	

game_file = 'C:/Users/matt/Desktop/ps2/Armored Core 3/Armored Core 3.iso'
file_size = os.path.getsize(game_file)
f = open(game_file, 'rb')
print('is_valid_udf', is_valid_udf(f, file_size))
sector_size = get_sector_size(f, file_size)
print('sector_size', sector_size)
go(f, file_size, sector_size)


