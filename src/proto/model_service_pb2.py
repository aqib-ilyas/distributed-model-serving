# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: model_service.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x13model_service.proto\x12\rmodel_service\"\x86\x01\n\nModelInput\x12\x0c\n\x04\x64\x61ta\x18\x01 \x03(\x05\x12\x39\n\x08metadata\x18\x02 \x03(\x0b\x32\'.model_service.ModelInput.MetadataEntry\x1a/\n\rMetadataEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\"\x1b\n\x0bModelOutput\x12\x0c\n\x04\x64\x61ta\x18\x01 \x03(\x05\"\x14\n\x12HealthCheckRequest\"%\n\x13HealthCheckResponse\x12\x0e\n\x06status\x18\x01 \x01(\t2\xab\x01\n\x0cModelService\x12\x42\n\x07process\x12\x19.model_service.ModelInput\x1a\x1a.model_service.ModelOutput\"\x00\x12W\n\x0chealth_check\x12!.model_service.HealthCheckRequest\x1a\".model_service.HealthCheckResponse\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'model_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _MODELINPUT_METADATAENTRY._options = None
  _MODELINPUT_METADATAENTRY._serialized_options = b'8\001'
  _globals['_MODELINPUT']._serialized_start=39
  _globals['_MODELINPUT']._serialized_end=173
  _globals['_MODELINPUT_METADATAENTRY']._serialized_start=126
  _globals['_MODELINPUT_METADATAENTRY']._serialized_end=173
  _globals['_MODELOUTPUT']._serialized_start=175
  _globals['_MODELOUTPUT']._serialized_end=202
  _globals['_HEALTHCHECKREQUEST']._serialized_start=204
  _globals['_HEALTHCHECKREQUEST']._serialized_end=224
  _globals['_HEALTHCHECKRESPONSE']._serialized_start=226
  _globals['_HEALTHCHECKRESPONSE']._serialized_end=263
  _globals['_MODELSERVICE']._serialized_start=266
  _globals['_MODELSERVICE']._serialized_end=437
# @@protoc_insertion_point(module_scope)
