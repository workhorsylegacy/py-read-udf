#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# A module for reading DVD ISOs with Python 2 & 3
# See Universal Disk Format (ISO/IEC 13346 and ECMA-167) for details
# http://www.ecma-international.org/publications/files/ECMA-TR/TR-071.pdf
# http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-167.pdf
# http://www.osta.org/specs/pdf/udf260.pdf
# http://en.wikipedia.org/wiki/Universal_Disk_Format

import sys, os

HEADER_SIZE = 1024 * 32
SECTOR_SIZE = 1024 * 2 # This should not be hard coded

def to_int(byte):
	import struct
	return struct.unpack('B', byte)[0]

def to_uint16(buffer, offset):
	left = ((to_int(buffer[offset + 1]) << 8) & 0xFF00)
	right = ((to_int(buffer[offset + 0]) << 0) & 0x00FF)
	return (left | right)

def to_uint32(buffer, offset):
	a = ((to_int(buffer[offset + 3]) << 24) & 0xFF000000)
	b = ((to_int(buffer[offset + 2]) << 16) & 0x00FF0000)
	c = ((to_int(buffer[offset + 1]) << 8) & 0x0000FF00)
	d = ((to_int(buffer[offset + 0]) << 0) & 0x000000FF)
	return(a | b | c | d)


class TagIdentifier(object): # enum
	none = 0
	PrimaryVolumeDescriptor = 1
	AnchorVolumeDescriptorPointer = 2
	ImplementationUseVolumeDescriptor = 4
	PartitionDescriptor = 5
	LogicalVolumeDescriptor = 6
	UnallocatedSpaceDescriptor = 7
	TerminatingDescriptor = 8
	LogicalVolumeIntegrityDescriptor = 9
	FileSetDescriptor = 256
	FileIdentifierDescriptor = 257
	FileEntry = 261
	ExtendedAttributeHeaderDescriptor = 262


# page 14 or http://www.ecma-international.org/publications/files/ECMA-TR/TR-071.pdf
class AnchorVolumeDescriptorPointer(object):
	def __init__(self, buffer):
		self._is_valid = True

		self.descriptor_tag = DescriptorTag(buffer)
		self.main_volume_descriptor_squence_extent = buffer[16 : 24]
		self.reserve_volume_descriptor_squence_extent = buffer[24 : 32]
		self.reserved = buffer[32 : 512]

	def get_is_valid(self):
		return self._is_valid
	is_valid = property(get_is_valid)


class DescriptorTag(object):
	def __init__(self, buffer):
		self._is_valid = True
		
		if len(buffer) < 16:
			self._is_valid = False
			return
		
		if to_uint16(buffer, 0) == 0:
			self._is_valid = False

		self.descriptor_tag = to_uint16(buffer, 0)
		self.descriptor_version = to_uint16(buffer, 2)
		self.tag_check_sum = to_int(buffer[4])
		self.reserved = to_int(buffer[5])
		self.tag_serial_number = to_uint16(buffer, 6)
		self.descriptor_crc = to_uint16(buffer, 8)
		self.descriptor_crc_length = to_uint16(buffer, 10)
		self.tag_location = to_uint32(buffer, 12)

		# Make sure the checksum matches
		check_sum = 0
		for i in range(16):
			if i == 4:
				continue
			check_sum += to_int(buffer[i])

		# Truncate int to uint8
		while check_sum > 256:
			check_sum -= 256

		self._is_valid = (check_sum == self.tag_check_sum)

	def get_is_valid(self):
		return self._is_valid
	is_valid = property(get_is_valid)


# page 27 of http://www.ecma-international.org/publications/files/ECMA-TR/TR-071.pdf
class PrimaryVolumeDescriptor(object):
	def __init__(self, buffer):
		self._is_valid = True

		if len(buffer) < SECTOR_SIZE:
			self._is_valid = False
			return

		self.volume_descriptor_type = int(buffer[0])
		self.standard_identifier = buffer[1 : 6]
		#print(self.standard_identifier)
		self.volume_descriptor_version = buffer[6 : 7]
		self.unused_field_01 = buffer[7 : 8]
		self.system_identifier = buffer[8 : 40]
		self.volume_identifier = buffer[40 : 72]
		self.unused_field_02 = buffer[72 : 80]
		self.volume_space_size = buffer[80 : 88]
		self.unused_field_03 = buffer[88 : 120]
		self.volume_set_size = buffer[120 : 124]
		self.volume_sequence_number = buffer[124 : 128]
		self.logical_block_size = buffer[124 : 128]
		self.path_table_size = buffer[132 : 140]
		self.location_of_occurrence_of_type_l_path_table = buffer[140 : 144]
		self.location_of_optional_occurrence_of_type_l_path_table = buffer[144 : 148]
		self.location_of_occurrence_of_type_m_path_table = buffer[148 : 152]
		self.location_of_optional_occurrence_of_type_m_path_table = buffer[152 : 156]
		self.directory_record_for_root_directory = buffer[156 : 190]
		self.volume_set_identifier = buffer[190 : 318]
		self.publisher_identifier = buffer[318 : 446]
		self.data_preparer_identifier = buffer[446 : 574]
		self.application_identifier = buffer[574 : 702]
		self.copyright_file_identifier = buffer[702 : 739]
		self.abstract_file_identifier = buffer[739 : 776]
		self.bibliographic_file_identifier = buffer[776 : 813]
		self.volume_creation_date_and_time = buffer[813 : 830]
		self.volume_modification_date_and_time = buffer[830 : 847]
		self.volume_expiration_date_and_time = buffer[847 : 864]
		self.volume_effective_date_and_time = buffer[864 : 881]
		self.file_structure_version = int(buffer[881])
		self.reserved_01 = buffer[882 : 883]
		self.application_use = buffer[883 : 1395]
		self.reserved_02 = buffer[1395 : 2048]

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
		structure_type = to_int(buffer[0])
		standard_identifier = buffer[1 : 6]
		structure_version = to_int(buffer[6])
		structure_data = buffer[7 : 2048]
		
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
	sizes = [2048, 512, 4096, 1024]
	for size in sizes:
		# Skip this size if the file is too small for all the sectors
		if file_size < 257 * size:
			continue

		# Move to the last logical sector
		file.seek(256 * size)

		# Read the Descriptor Tag
		buffer = file.read(512)
		tag = DescriptorTag(buffer)

		# Skip if not valid
		if not tag.is_valid:
			continue

		#print(tag.descriptor_tag)
		'''
		print(tag.descriptor_version)
		print(tag.tag_check_sum)
		print(tag.tag_serial_number)
		print(tag.descriptor_crc)
		print(tag.descriptor_crc_length)
		print(tag.tag_location)
		'''

		# If the last sector is an Anchor Volume Descriptor Pointer, the sector size matches
		if tag.descriptor_tag == TagIdentifier.AnchorVolumeDescriptorPointer and tag.tag_location == 256:
			return size

	return 0

def go(file, file_size, sector_size):
	if file_size < 257 * sector_size:
		return

	for sector in range(256):
		# Move to the last logical sector
		file.seek(sector * sector_size)

		# Read the Descriptor Tag
		buffer = file.read(sector_size)
		tag = DescriptorTag(buffer)

		# Skip if not valid
		if not tag.is_valid:
			continue

		print(tag.descriptor_tag)
		'''
		print(tag.descriptor_version)
		print(tag.tag_check_sum)
		print(tag.tag_serial_number)
		print(tag.descriptor_crc)
		print(tag.descriptor_crc_length)
		'''
		if tag.descriptor_tag == TagIdentifier.AnchorVolumeDescriptorPointer:
			AnchorVolumeDescriptorPointer(buffer)
		#elif tag.descriptor_tag == TagIdentifier.
		
		
		# Read the Descriptor Tag
		anchor_volume_descriptor_pointer = buffer[0 : 16]
		main_volume_descriptor_squence_extent = buffer[16 : 24]
		reserve_volume_descriptor_squence_extent = buffer[16 : 24]
		
		# FIXME: Get these for the main and reserve
		'''
		avdp contains main and reserve volume descriptors
		Primary
		Volume Descriptor
		Implementation Use Volume Descriptor
		Partition Descriptor
		Logical Volume Descriptor
		Unallocated Space Descriptor
		Terminating Descriptor
		'''
	

game_file = 'C:/Users/matt/Desktop/ps2/Armored Core 3/Armored Core 3.iso'
file_size = os.path.getsize(game_file)
f = open(game_file, 'rb')
print('is_valid_udf', is_valid_udf(f, file_size))
print('get_sector_size', get_sector_size(f, file_size))
go(f, file_size, 2048)


