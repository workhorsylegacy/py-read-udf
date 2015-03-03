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


# "2.1.5 Entity Identifier" of http://www.osta.org/specs/pdf/udf260.pdf
class EntityIdType(object): # enum
	unknown = 0
	DomainIdentifier = 1
	UDFIdentifier = 2
	ImplementationIdentifier = 3
	ApplicationIdentifier = 4


# page 15 of http://www.osta.org/specs/pdf/udf260.pdf
# 1/12 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class EntityID(BaseTag):
	def __init__(self, entity_id_type, buffer, start):
		super(EntityID, self).__init__(32, buffer, start)

		self.entity_id_type = entity_id_type
		self.flags = to_uint8(buffer[start + 0])
		self.identifier = buffer[start + 1 : start + 24]
		self.identifier_suffix = buffer[start + 24 : start + 32]

		#print('self.flags', self.flags)
		#print('self.identifier', self.identifier)
		#print('self.identifier_suffix', self.identifier_suffix)

		# Make sure the flag is always 0
		#if self.flags != 0:
		#	raise Exception("EntityID flags was not zero")


# page 3/4 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
# page 4/4 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
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
	FileSetDescriptor = 256


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


class PhysicalPartition(object):
	def __init__(self, start, size):
		self._start = start
		self._size = size


class Type1Partition(object):
	def __init__(self, logical_volume_descriptor, partition_map, physical_partition):
		self.logical_volume_descriptor = logical_volume_descriptor
		self.partition_map = partition_map
		self.physical_partition = physical_partition

	def get_logical_block_size(self):
		return self.logical_volume_descriptor.logical_block_size
	logical_block_size = property(get_logical_block_size)

# page 4/17 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class FileSetDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(PrimaryVolumeDescriptor, self).__init__(512, buffer, start)

		self.descriptor_tag = DescriptorTag(buffer)
		self._assert_tag_identifier(TagIdentifier.FileSetDescriptor)

		self.recording_date_and_time = buffer[16 : 28] # FIXME: timestamp
		self.interchange_level = to_uint16(buffer, 28)
		self.maximum_interchange_level = to_uint16(buffer, 30)
		self.character_set_list = to_uint32(buffer, 32)
		self.maximum_character_set_list = to_uint32(buffer, 36)
		self.file_set_number = to_uint32(buffer, 40)
		self.file_set_descriptor_number = to_uint32(buffer, 44)
		self.logical_volume_identifier_character_set = buffer[48 : 112] # FIXME: charspec
		self.logical_volume_identifier = to_dstring(buffer, 112, 128)
		self.file_set_character_set = buffer[240 : 274] # FIXME: charspec
		self.file_set_identifier = to_dstring(buffer, 304, 32)
		self.copyright_file_identifier = to_dstring(buffer, 336, 32)
		self.abstract_file_identifier = to_dstring(buffer, 368, 32)
		self.root_directory_icb = buffer[400 : 416] # FIXME: long_ad
		self.domain_identifier = EntityId(EntityIdType.DomainIdentifier, buffer, 416)
		self.next_extent = buffer[448 : 464] # FIXME: long_ad
		self.system_stream_directory_icb = buffer[464 : 480] # FIXME: long_ad
		self.reserved = buffer[480 : 512]

		self._assert_reserve_space(buffer, 480, 32)


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
		self.application_identifier = EntityID(EntityIdType.ApplicationIdentifier, buffer, 344)
		self.recording_date_and_time = buffer[376 : 388] # FIXME: timestamp
		self.implementation_identifier = EntityID(EntityIdType.ImplementationIdentifier, buffer, 388)
		self.implementation_use = buffer[420 : 484]
		self.predecessor_volume_descriptor_sequence_location = to_uint32(buffer, 484)
		self.flags = to_uint16(buffer, 488)
		self.reserved = buffer[490 : 512]

		self._assert_reserve_space(buffer, start + 490, 22)


# page 3/17 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
# page 45 of http://www.osta.org/specs/pdf/udf260.pdf
class PartitionDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(PartitionDescriptor, self).__init__(512, buffer, start)

		self.descriptor_tag = DescriptorTag(buffer)
		self._assert_tag_identifier(TagIdentifier.PartitionDescriptor)

		self.volume_descriptor_sequence_number = to_uint32(buffer, 16)
		self.partition_flags = to_uint16(buffer, 20)
		self.partition_number = to_uint16(buffer, 22)
		self.partition_contents = EntityID(EntityIdType.UDFIdentifier, buffer, 24)
		self.partition_contents_use = buffer[56 : 184]
		self.access_type = to_uint32(buffer, 184)
		self.partition_starting_location = to_uint32(buffer, 188)
		self.partition_length = to_uint32(buffer, 192)
		self.implementation_identifier = EntityID(EntityIdType.ImplementationIdentifier, buffer, 196)
		self.implementation_use = buffer[228 : 356]
		self.reserved = buffer[356 : 512]

		# If the partition has allocated volume space
		if self.partition_flags == 1:
			pass
		'''
		print('self.volume_descriptor_sequence_number', self.volume_descriptor_sequence_number)
		print('self.partition_flags', self.partition_flags)
		print('self.partition_number', self.partition_number)
		print('self.partition_contents', self.partition_contents)
		print('self.partition_contents_use', self.partition_contents_use)
		print('self.partition_starting_location', self.partition_starting_location)
		'''
		self._assert_reserve_space(buffer, start + 356, 156)


# page 3/19 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
# page 24 of http://www.osta.org/specs/pdf/udf260.pdf
class LogicalVolumeDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(LogicalVolumeDescriptor, self).__init__(512, buffer, start)

		self.descriptor_tag = DescriptorTag(buffer)
		self._assert_tag_identifier(TagIdentifier.LogicalVolumeDescriptor)

		self.volume_descriptor_sequence_number = to_uint32(buffer, 16)
		self.descriptor_character_set = buffer[20 : 84] # FIXME: charspec
		self.logical_volume_identifier = to_dstring(buffer, 84, 128)
		self.logical_block_size = to_uint32(buffer, 128)
		self.domain_identifier = EntityID(EntityIdType.DomainIdentifier, buffer, 216)
		self.logical_volume_contents_use = buffer[248 : 264]
		self.map_table_length = to_uint32(buffer, 264)
		self.number_of_partition_maps = to_uint32(buffer, 268)
		self.implementation_identifier = EntityID(EntityIdType.ImplementationIdentifier, buffer, 272)
		self.implementation_use = buffer[304 : 432]
		self.integrity_sequence_extent = ExtentDescriptor(buffer, 432)
		self._raw_partition_maps = buffer[440 : 512]

		if not "*OSTA UDF Compliant" in self.domain_identifier.identifier:
			raise Exception("Logical Volume is not OSTA compliant")

	# "10.6.13 Partition Maps (BP 440)" of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
	def get_partition_maps(self):
		buffer = self._raw_partition_maps
		retval = []
		part_start = 0
		for i in range(self.number_of_partition_maps):
			partition_type = to_uint8(buffer[part_start])
			partitioin = None
			if partition_type == 1:
				partition = Type1PartitionMap(buffer, part_start)
			else:
				raise Exception("Unexpected partition type {0}".format(partition_type))

			retval.append(partition)
			part_start += partition.size

		return retval
	partition_maps = property(get_partition_maps)

	# "2.2.4.4 byte LogicalVolumeContentsUse[16]" of http://www.osta.org/specs/pdf/udf260.pdf
	def get_file_set_descriptor_location(self):
		return LongAllocationDescriptor(self.logical_volume_contents_use)
	file_set_descriptor_location = property(get_file_set_descriptor_location)


# page 60 of http://www.osta.org/specs/pdf/udf260.pdf
class LongAllocationDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(LongAllocationDescriptor, self).__init__(16, buffer, start)

		self.extent_length = to_uint32(buffer, 0)
		self.extent_location = LogicalBlockAddress(buffer, 4)
		self.implementation_use = buffer[10 : 16]


# page 4/3 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class LogicalBlockAddress(BaseTag):
	def __init__(self, buffer, start = 0):
		super(LogicalBlockAddress, self).__init__(6, buffer, start)
		self.logical_block_number = to_uint32(buffer, 0)
		self.partition_reference_number = to_uint16(buffer, 4)


class TerminatingDescriptor(BaseTag):
	def __init__(self, buffer, start = 0):
		super(TerminatingDescriptor, self).__init__(512, buffer, start)

	# FIXME: Add the rest


# page 3/21 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class Type1PartitionMap(BaseTag):
	def __init__(self, buffer, start):
		super(Type1PartitionMap, self).__init__(6, buffer, start)

		self.partition_map_type = to_uint8(buffer[start + 0])
		self.partition_map_length = to_uint8(buffer[start + 1])
		self.volume_sequence_number = to_uint16(buffer, start + 2)
		self.partition_number = to_uint16(buffer, start + 4)

		if not self.partition_map_type == 1:
			raise Exception("Type 1 Partition Map Type was {0} instead of 1.".format(self.partition_map_type))

		if not self.partition_map_length == self.size:
			raise Exception("Type 1 Partition Map Length was {0} instead of {1}.".format(self.partition_map_length, self.size))


# page 3/22 of http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
class Type2PartitionMap(BaseTag):
	def __init__(self, buffer, start):
		super(Type2PartitionMap, self).__init__(64, buffer, start)

		self.partition_map_type = to_uint8(buffer[start + 0])
		self.partition_map_length = to_uint8(buffer[start + 1])
		self.partition_type_identifier = EntityID(EntityIdType.UDFIdentifier, start + 4, start + 32)

		if not self.partition_map_type == 2:
			raise Exception("Type 2 Partition Map Type was {0} instead of 2.".format(self.partition_map_type))

		if not self.partition_map_length == self.size:
			raise Exception("Type 2 Partition Map Length was {0} instead of {1}.".format(self.partition_map_length, self.size))


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
		
	# Look through all the sectors and find the partition descriptor
	logical_volume_descriptor = None
	terminating_descriptor = None
	physical_partitions = {}
	logical_partitions = []
	for sector in range(pvd_sector, 257):
		# Move to the sector start
		file.seek(sector * sector_size)

		# Read the Descriptor Tag
		buffer = file.read(16)
		tag = None
		try:
			tag = DescriptorTag(buffer)
		# Skip if not valid
		except:
			continue

		# Move back to the start of the sector
		file.seek(sector * sector_size)
		buffer = file.read(512)
		
		#print('tag.tag_identifier', tag.tag_identifier)

		if tag.tag_identifier == TagIdentifier.PrimaryVolumeDescriptor:
			#print(sector, 'PrimaryVolumeDescriptor')
			desc = PrimaryVolumeDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.AnchorVolumeDescriptorPointer:
			#print(sector, 'AnchorVolumeDescriptorPointer')
			anchor = AnchorVolumeDescriptorPointer(buffer)
		elif tag.tag_identifier == TagIdentifier.VolumeDescriptorPointer:
			#print(sector, 'VolumeDescriptorPointer')
			pass #VolumeDescriptorPointer(buffer)
		elif tag.tag_identifier == TagIdentifier.ImplementationUseVolumeDescriptor:
			#print(sector, 'ImplementationUseVolumeDescriptor')
			pass #ImplementationUseVolumeDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.PartitionDescriptor:
			partition_descriptor = PartitionDescriptor(buffer)
			start = partition_descriptor.partition_starting_location * sector_size
			length = partition_descriptor.partition_length * sector_size
			physical_partition = PhysicalPartition(start, length)
			physical_partitions[partition_descriptor.partition_number] = physical_partition
			print(sector, 'PartitionDescriptor')
		elif tag.tag_identifier == TagIdentifier.LogicalVolumeDescriptor:
			logical_volume_descriptor = LogicalVolumeDescriptor(buffer)
			print(sector, 'LogicalVolumeDescriptor')
		elif tag.tag_identifier == TagIdentifier.UnallocatedSpaceDescriptor:
			#print(sector, 'UnallocatedSpaceDescriptor')
			pass #UnallocatedSpaceDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.TerminatingDescriptor:
			print(sector, 'TerminatingDescriptor')
			terminating_descriptor = TerminatingDescriptor(buffer)
		elif tag.tag_identifier == TagIdentifier.LogicalVolumeIntegrityDescriptor:
			#print(sector, 'LogicalVolumeIntegrityDescriptor')
			pass #LogicalVolumeIntegrityDescriptor(buffer)
		elif tag.tag_identifier != 0:
			print("Unexpected Descriptor Tag :{0}".format(tag.tag_identifier))

		if logical_volume_descriptor and partition_descriptor and terminating_descriptor:
			break

	# Make sure we have all the segments we need
	if not logical_volume_descriptor or not partition_descriptor or not terminating_descriptor:
		raise Exception("Failed to get the required segments")


	#print('logical_volume_descriptor.logical_volume_contents_use', logical_volume_descriptor.logical_volume_contents_use)
	print('logical_volume_descriptor.map_table_length', logical_volume_descriptor.map_table_length)
	print('logical_volume_descriptor.number_of_partition_maps', logical_volume_descriptor.number_of_partition_maps)
	print('logical_volume_descriptor.logical_volume_contents_use', logical_volume_descriptor.logical_volume_contents_use)
	#	logical_volume_descriptor.implementation_identifier = EntityID(EntityIdType.ImplementationIdentifier, buffer, 272)
	#	logical_volume_descriptor.implementation_use = buffer[304 : 432]
	#	logical_volume_descriptor.integrity_sequence_extent = ExtentDescriptor(buffer, 432)
	#	logical_volume_descriptor.partition_maps = buffer[440 : 440 + (self.map_table_length * self.number_of_partition_maps)]

	# Get all the logical partitions
	for map in logical_volume_descriptor.partition_maps:
		print(map.partition_map_type)

		if isinstance(map, Type1PartitionMap):
			partition_number = map.partition_number
			physical_Partition = physical_partitions[partition_number]
			partition = Type1Partition(logical_volume_descriptor, map, physical_Partition)
			logical_partitions.append(partition)
		elif isinstance(map, Type2PartitionMap):
			raise NotImplementedError("FIXME: Add support for Type 2 Partitions.")

	logical_volume_descriptor.file_set_descriptor_location
	ext_buffer = read_extent(logical_partitions, logical_volume_descriptor.file_set_descriptor_location)


def read_extent(logical_partitions, extent):
	print('extent.extent_location.partition_reference_number', extent.extent_location.partition_reference_number)
	logical_partition = logical_partitions[extent.extent_location.partition_reference_number]
	start = extent.extent_location.logical_block_number * logical_partition.logical_block_size
	return logical_partition.content.read(pos, extent.extent_length)


game_file = 'C:/Users/matt/Desktop/ps2/Armored Core 3/Armored Core 3.iso'
file_size = os.path.getsize(game_file)
f = open(game_file, 'rb')
print('is_valid_udf', is_valid_udf(f, file_size))
sector_size = get_sector_size(f, file_size)
print('sector_size', sector_size)
go(f, file_size, sector_size)


