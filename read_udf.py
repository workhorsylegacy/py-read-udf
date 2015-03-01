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

def to_uint16(buffer, start = 0):
	left = ((to_uint8(buffer[start + 1]) << 8) & 0xFF00)
	right = ((to_uint8(buffer[start + 0]) << 0) & 0x00FF)
	return (left | right)

def to_uint32(buffer, start = 0):
	a = ((to_uint8(buffer[start + 3]) << 24) & 0xFF000000)
	b = ((to_uint8(buffer[start + 2]) << 16) & 0x00FF0000)
	c = ((to_uint8(buffer[start + 1]) << 8) & 0x0000FF00)
	d = ((to_uint8(buffer[start + 0]) << 0) & 0x000000FF)
	return(a | b | c | d)


class BaseTag(object):
	def __init__(self, size, buffer, start):
		self._size = size

		self._assert_size(buffer, start)

	def get_size(self):
		return self._size
	size = property(get_size)

	# Make sure there is enough space
	def _assert_size(self, buffer, start):
		if len(buffer) - start < self._size:
			raise Exception("{0} requires {1} bytes, but buffer only has {2}".format(type(self), self._size, len(buffer) - start))

	# Make sure the checksums match
	def _assert_checksum(self, buffer, start, expected_checksum):
		checksum = 0
		for i in range(16):
			if i == 4:
				continue
			checksum += to_uint8(buffer[start + i])

		# Truncate int to uint8
		while checksum > 256:
			checksum -= 256

		if not checksum == expected_checksum:
			raise Exception("Checksum was {0}, but {1} was expected".format(checksum, expected_checksum))

	# Make sure it is the correct type of tag
	def _assert_tag_identifier(self, expected_tag_identifier):
		if not self.descriptor_tag.tag_identifier == expected_tag_identifier:
			raise Exception("Expected Tag Identifier {0}, but was {1}".format(expected_tag_identifier, self.descriptor_tag.tag_identifier))

	# Make sure the reserved space is all zeros
	def _assert_reserve_space(self, buffer, start, length):
		for n in buffer[start : start + length]:
			if not to_uint8(n) == 0:
				raise Exception("Reserve space at {0} was not zero.".format(start))


class ApplicationIdentifier(BaseTag):
	def __init__(self, buffer, start):
		super(ApplicationIdentifier, self).__init__(32, buffer, start)

		self.flags = to_uint8(buffer[start + 0])
		self.identifier = buffer[start + 1 : start + 24]
		self.identifier_suffix = buffer[start + 24 : start + 32]


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
class DescriptorTag(BaseTag):
	def __init__(self, buffer, start = 0):
		super(DescriptorTag, self).__init__(16, buffer, start)

		self.tag_identifier = to_uint16(buffer, start + 0)
		self.descriptor_version = to_uint16(buffer, start + 2)
		self.tag_check_sum = to_uint8(buffer[start + 4])
		self.reserved = to_uint8(buffer[start + 5])
		self.tag_serial_number = to_uint16(buffer, start + 6)
		self.descriptor_crc = to_uint16(buffer, start + 8)
		self.descriptor_crc_length = to_uint16(buffer, start + 10)
		self.tag_location = to_uint32(buffer, start + 12)

		# Make sure the identifier is known
		if self.tag_identifier == TagIdentifier.unknown:
			raise Exception("Tag Identifier was unknown")

		self._assert_checksum(buffer, start, self.tag_check_sum)
		self._assert_reserve_space(buffer, start + 5, 1)


# page 3/3 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class ExtentDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(ExtentDescriptor, self).__init__(8, buffer, start)

		self.extent_length = to_uint32(buffer, start)
		self.extent_location = to_uint32(buffer, start + 4)


# page 3/15 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class AnchorVolumeDescriptorPointer(BaseTag):
	def __init__(self, buffer, start = 0):
		super(AnchorVolumeDescriptorPointer, self).__init__(512, buffer, start)

		self.descriptor_tag = DescriptorTag(buffer)
		self._assert_tag_identifier(TagIdentifier.AnchorVolumeDescriptorPointer)

		self.main_volume_descriptor_sequence_extent = ExtentDescriptor(buffer, 16)
		self.reserve_volume_descriptor_sequence_extent = ExtentDescriptor(buffer, 24)
		self.reserved = buffer[32 : 512]

		self._assert_reserve_space(buffer, start + 32, 480)


# page 12 of http://www.osta.org/specs/pdf/udf260.pdf
# page 1/10 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
def to_dstring(buffer, start, max_length):
	raw = buffer[start : start + max_length]
	length = to_uint8(raw[0])
	retval = raw[1 : 1 + length]
	#print('dstring', retval)
	return retval


# page 3/12 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class PrimaryVolumeDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(PrimaryVolumeDescriptor, self).__init__(512, buffer, start)

		self.descriptor_tag = DescriptorTag(buffer)
		self._assert_tag_identifier(TagIdentifier.PrimaryVolumeDescriptor)

		self.volume_descriptor_sequence_number = to_uint32(buffer, 16)
		self.primary_volume_descriptor_number = to_uint32(buffer, 20)
		self.volume_identifier = to_dstring(buffer, 24, 32)
		self.volume_sequence_number = to_uint16(buffer, 56)
		self.maximum_volume_sequence_number = to_uint16(buffer, 58)
		self.interchange_level = to_uint16(buffer, 60)
		self.maximum_interchange_level = to_uint16(buffer, 62)
		self.character_set_list = to_uint32(buffer, 64)
		self.maximum_character_set_list = to_uint32(buffer, 68)
		self.volume_set_identifier = to_dstring(buffer, 72, 128)
		self.descriptor_character_set = buffer[200 : 264] # FIXME: char spec
		self.expalnatory_character_set = buffer[264 : 328] # FIXME: char spec
		self.volume_abstract = ExtentDescriptor(buffer, 328)
		self.volume_copyright_notice = ExtentDescriptor(buffer, 336)
		self.application_identifier = ApplicationIdentifier(buffer, 344)
		self.recording_date_and_time = buffer[376 : 388] # FIXME: timestamp
		self.implementation_identifier = buffer[388 : 420] # FIXME: regid
		self.implementation_use = buffer[420 : 484]
		self.predecessor_volume_descriptor_sequence_location = to_uint32(buffer, 484)
		self.flags = to_uint16(buffer, 488)
		self.reserved = buffer[490 : 512]

		self._assert_reserve_space(buffer, start + 490, 22)


# page 3/17 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class PartitionDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(PartitionDescriptor, self).__init__(512, buffer, start)

		self.descriptor_tag = DescriptorTag(buffer)
		self._assert_tag_identifier(TagIdentifier.PartitionDescriptor)

		self.volume_descriptor_sequence_number = to_uint32(buffer, 16)
		self.partition_flags = to_uint16(buffer, 20)
		self.partition_number = to_uint16(buffer, 22)
		self.partition_contents = buffer[24 : 56] # FIXME regid
		self.partition_contents_use = buffer[56 : 184]
		self.access_type = to_uint32(buffer, 184)
		self.partition_starting_location = to_uint32(buffer, 188)
		self.partition_length = to_uint32(buffer, 192)
		self.implementation_identifier = buffer[196 : 228] # FIXME: regid
		self.implementation_use = buffer[228 : 356]
		self.reserved = buffer[356 : 512]

		self._assert_reserve_space(buffer, start + 356, 156)


# page 3/19 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class LogicalVolumeDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(LogicalVolumeDescriptor, self).__init__(512, buffer, start)

		self.descriptor_tag = DescriptorTag(buffer)
		self._assert_tag_identifier(TagIdentifier.LogicalVolumeDescriptor)

		self.volume_descriptor_sequence_number = to_uint32(buffer, 16)
		self.descriptor_character_set = buffer[20 : 84] # FIXME: charspec
		self.logical_volume_identifier = to_dstring(buffer, 84, 128)
		self.logical_block_size = to_uint32(buffer, 128)
		self.domain_identifier = buffer[216 : 248] # FIXME: regid
		self.logical_volume_centents_use = buffer[248 : 264]
		self.map_table_length = to_uint32(buffer, 264)
		self.number_of_partition_maps = to_uint32(buffer, 268)
		self.implementation_identifier = buffer[272 : 304] # FIXME: regid
		self.implementation_use = buffer[304 : 432]
		self.integrity_sequence_extent = ExtentDescriptor(buffer, 432)
		self.partition_maps = buffer[440 : 440 + (self.map_table_length * self.number_of_partition_maps)]


# FIXME: This assumes the sector size is 2048
def is_valid_udf(file, file_size):
	# Move to the start of the file
	file.seek(0)

	# Make sure there is enough space for a header and sector
	if file_size < HEADER_SIZE + SECTOR_SIZE:
		return False

	# Move past 32K of empty space
	file.seek(HEADER_SIZE)

	is_valid = True
	has_bea, has_vsd, has_tea = False, False, False

	# Look at each sector
	while(is_valid):
		# Read the next sector
		buffer = file.read(SECTOR_SIZE)
		if len(buffer) < SECTOR_SIZE:
			break

		# Get the sector meta data
		structure_type = to_uint8(buffer[0])
		standard_identifier = buffer[1 : 6]
		structure_version = to_uint8(buffer[6])

		# Check if we have the beginning, middle, or end
		if standard_identifier in ['BEA01']:
			has_bea = True
		elif standard_identifier in ['NSR02', 'NSR03']:
			has_vsd = True
		elif standard_identifier in ['TEA01']:
			has_tea = True
		elif standard_identifier in ['BOOT2', 'CD001', 'CDW02']:
			pass
		else:
			is_valid = False

	return has_bea and has_vsd and has_tea

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
		tag = None
		try:
			tag = DescriptorTag(buffer)
		# Skip if the tag is not valid
		except:
			continue

		# Skip if the tag thinks it is at the wrong sector
		if not tag.tag_location == 256:
			continue

		# Skip if the sector is not an Anchor Volume Description Pointer
		if not tag.tag_identifier == TagIdentifier.AnchorVolumeDescriptorPointer:
			continue

		# Got the correct size
		return size

	raise Exception("Could not get sector size.")

def go(file, file_size, sector_size):
	if file_size < 257 * sector_size:
		return

	# "5.2 UDF Volume Structure and Mount Procedure" of https://sites.google.com/site/udfintro/
	# Read the Anchor VD Pointer
	sector = 256
	file.seek(sector * sector_size)
	buffer = file.read(512)
	tag = DescriptorTag(buffer[0 : 16])
	if not tag.tag_identifier == TagIdentifier.AnchorVolumeDescriptorPointer:
		exit(1)
	avdp = AnchorVolumeDescriptorPointer(buffer)
	
	# Get the location of the primary volume descriptor
	pvd_sector = avdp.main_volume_descriptor_sequence_extent.extent_location
		
	logical_volume_descriptor = None
	partition_descriptor = None
	for sector in range(pvd_sector, 257):
		# Move to the sector start
		file.seek(sector * sector_size)

		# Read the Descriptor Tag
		buffer = file.read(16)
		tag = None

		# Skip if not valid
		try:
			tag = DescriptorTag(buffer)
		except:
			continue

		# Move back to the start of the sector
		file.seek(sector * sector_size)
		buffer = file.read(512)
		
		print('tag.tag_identifier', tag.tag_identifier)

		if tag.tag_identifier == TagIdentifier.PrimaryVolumeDescriptor:
			print(sector, 'PrimaryVolumeDescriptor')
			desc = PrimaryVolumeDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.AnchorVolumeDescriptorPointer:
			print(sector, 'AnchorVolumeDescriptorPointer')
			anchor = AnchorVolumeDescriptorPointer(buffer)
		elif tag.tag_identifier == TagIdentifier.VolumeDescriptorPointer:
			print(sector, 'VolumeDescriptorPointer')
			pass #VolumeDescriptorPointer(buffer)
		elif tag.tag_identifier == TagIdentifier.ImplementationUseVolumeDescriptor:
			print(sector, 'ImplementationUseVolumeDescriptor')
			pass #ImplementationUseVolumeDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.PartitionDescriptor:
			partition_descriptor = PartitionDescriptor(buffer)
			print(sector, 'PartitionDescriptor')
			pass #PartitionDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.LogicalVolumeDescriptor:
			logical_volume_descriptor = LogicalVolumeDescriptor(buffer)
			print(sector, 'LogicalVolumeDescriptor')
			pass #LogicalVolumeDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.UnallocatedSpaceDescriptor:
			print(sector, 'UnallocatedSpaceDescriptor')
			pass #UnallocatedSpaceDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.TerminatingDescriptor:
			print(sector, 'TerminatingDescriptor')
			pass #TerminatingDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.LogicalVolumeIntegrityDescriptor:
			print(sector, 'LogicalVolumeIntegrityDescriptor')
			pass #LogicalVolumeIntegrityDescriptor(buffer)
		elif tag.tag_identifier != 0:
			print("Unexpected Descriptor Tag :{0}".format(tag.tag_identifier))
	

game_file = 'C:/Users/matt/Desktop/ps2/Armored Core 3/Armored Core 3.iso'
file_size = os.path.getsize(game_file)
f = open(game_file, 'rb')
print('is_valid_udf', is_valid_udf(f, file_size))
sector_size = get_sector_size(f, file_size)
print('sector_size', sector_size)
go(f, file_size, sector_size)


