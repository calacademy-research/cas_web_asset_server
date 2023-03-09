from attachment_utils import AttachmentUtils
import datetime
from uuid import uuid4
import os, re, sys
from image_client import ImageClient
from db_utils import DbUtils, InvalidFilenameError, DatabaseInconsistentError
import collections

TMP_JPG = "./tmp_jpg"
import logging
import subprocess
from specify_db import SpecifyDb
import shutil
from os import listdir
from os.path import isfile, join


class ConvertException(Exception):
    pass


# class FilePath():
#     def __init__(self, filepath):
#         cur_filename = os.path.basename(filepath)
#
#         cur_file_base, cur_file_ext = cur_filename.split(".")
#
#         self.full_path = filepath
#         self.filename = cur_filename
#         self.basename = cur_file_base
#         self.ext = cur_file_ext
#
#     def __str__(self):
#         return self.full_path


class Importer:
    def __init__(self, db_config_class, collection_name):
        self.logger = logging.getLogger('Client.importer')
        self.collection_name = collection_name
        self.specify_db_connection = SpecifyDb(db_config_class)
        self.image_client = ImageClient()
        self.attachment_utils = AttachmentUtils(self.specify_db_connection)
        self.duplicates_file = open(f'duplicates-{self.collection_name}.txt', 'w')

    def split_filepath(self,filepath):
        cur_filename = os.path.basename(filepath)
        cur_file_ext = cur_filename.split(".")[1]
        return cur_filename, cur_file_ext

    def tiff_to_jpg(self, tiff_filepath):
        basename = os.path.basename(tiff_filepath)
        if not os.path.exists(TMP_JPG):
            os.mkdir(TMP_JPG)
        else:
            shutil.rmtree(TMP_JPG)
            os.mkdir(TMP_JPG)
        file_name_no_extention, extention = basename.split('.')
        if extention != 'tif':
            self.logger.error(f"Bad filename, can't convert {tiff_filepath}")
            raise ConvertException(f"Bad filename, can't convert {tiff_filepath}")

        jpg_dest = os.path.join(TMP_JPG, file_name_no_extention + ".jpg")

        proc = subprocess.Popen(['convert', '-quality', '99', tiff_filepath, jpg_dest], stdout=subprocess.PIPE)
        output = proc.communicate(timeout=60)[0]
        onlyfiles = [f for f in listdir(TMP_JPG) if isfile(join(TMP_JPG, f))]
        if len(onlyfiles) == 0:
            raise ConvertException(f"No files producted from conversion")
        files_dict = {}
        for file in onlyfiles:
            files_dict[file] = os.path.getsize(os.path.join(TMP_JPG, file))

        sort_orders = sorted(files_dict.items(), key=lambda x: x[1], reverse=True)
        top = sort_orders[0][0]
        target = os.path.join(TMP_JPG, file_name_no_extention + ".jpg")
        os.rename(os.path.join(TMP_JPG, top), target)
        if len(onlyfiles) > 2:
            self.logger.info("multi-file case")

        return target, output

    def get_mime_type(self, filepath):
        mime_type = None
        if filepath.lower().endswith('.tif') or filepath.lower().endswith('.tiff'):
            mime_type = 'image/tiff'
        if filepath.lower().endswith('.jpg') or filepath.lower().endswith('.jpeg'):
            mime_type = 'image/jpeg'
        if filepath.lower().endswith('.gif'):
            mime_type = 'image/gif'
        if filepath.lower().endswith('.png'):
            mime_type = 'image/png'
        if filepath.lower().endswith('.pdf'):
            mime_type = 'application/pdf'
        return mime_type

    def import_to_specify_database(self, filepath, attach_loc, url, collection_object_id, agent_id, copyright=None):
        attachment_guid = uuid4()

        file_created_datetime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

        mime_type = self.get_mime_type(filepath)

        self.attachment_utils.create_attachment(storename=attach_loc,
                                                original_filename=os.path.basename(filepath),
                                                file_created_datetime=file_created_datetime,
                                                guid=attachment_guid,
                                                image_type=mime_type,
                                                url=url,
                                                agent_id=agent_id,
                                                copyright=copyright)
        attachment_id = self.attachment_utils.get_attachment_id(attachment_guid)
        ordinal = self.attachment_utils.get_ordinal_for_collection_object_attachment(collection_object_id)
        if ordinal is None:
            ordinal = 0
        else:
            ordinal += 1
        self.attachment_utils.create_collection_object_attachment(attachment_id, collection_object_id, ordinal,
                                                                  agent_id)

    def get_first_digits_from_filepath(self, filepath, field_size=9):
        basename = os.path.basename(filepath)
        ints = re.findall(r'\d+', basename)
        if len(ints) == 0:
            raise InvalidFilenameError("Can't get barcode from filename")
        int_digits = int(ints[0])
        string_digits = f"{int_digits}"
        string_digits = string_digits.zfill(field_size)
        self.logger.debug(f"extracting digits from {filepath} to get {string_digits}")
        return string_digits

    def format_filesize(self, num, suffix="B"):
        for unit in ["", "K", "M", "G", "T"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f} Yi{suffix}"

    #  Filepath is a list of three element lists - full filepath, the filename, and the extension.

    def clean_duplicate_files(self, filepath_list):
        basename_list = [os.path.basename(filepath.cur_basename) for filepath in filepath_list]
        basename_set = set(basename_list)
        filepath_only_list = [filepath.full_path for filepath in filepath_list]
        duplicates = [item for item, count in collections.Counter(basename_list).items() if count > 1]

        for duplicate in duplicates:
            res = [item for item in filepath_only_list if duplicate in item]
            self.duplicates_file.write(f'\nDuplicate: {duplicate}\n')

            for dupe_path in res:
                size = os.path.getsize(dupe_path)
                self.logger.debug(f"dupe_path: {dupe_path}")
                self.duplicates_file.write(f"\t {self.format_filesize(size)}: {dupe_path}\n")
        clean_list = []
        for keep_name in basename_set:
            for filepath in filepath_list:
                if keep_name in filepath:
                    clean_list.append(filepath)
        return clean_list

    def convert_if_required(self, filepath):
        jpg_found = False
        tif_found = False
        deleteme = None
        filename, filename_ext = self.split_filepath(filepath)
        if filename_ext == "jpg" or filename_ext == "jpeg":
            jpg_found = filepath
        if filename_ext == "tif" or filename_ext == "tiff":
            tif_found = filepath
        original_full_path = jpg_found
        if not jpg_found and tif_found:
            self.logger.debug(f"  Must create jpg for {filepath} from {tif_found}")
            try:
                jpg_found, output = self.tiff_to_jpg(tif_found)
                self.logger.info(f"Converted to: {jpg_found}")
            except TimeoutError:
                self.logger.error(f"Timeout converting {tif_found}")
            except subprocess.TimeoutExpired:
                self.logger.error(f"Timeout converting {tif_found}")
            except ConvertException:
                self.logger.error(f"  Conversion failure for {tif_found}; skipping.")
                return False

            if not os.path.exists(jpg_found):
                self.logger.error(f"  Conversion failure for {tif_found}; skipping.")
                self.logger.debug(f"Imagemagik output: \n\n{output}\n\n")
                return False
            deleteme = jpg_found
            original_full_path = tif_found
            if not jpg_found and tif_found:
                self.logger.debug(f"  No valid files for {filepath.full_path}")
                return False
        if os.path.getsize(jpg_found) < 1000:
            self.logger.info(f"This image is too small; {os.path.getsize(jpg_found)}, skipping.")
            return False
        return deleteme

    def upload_filepath_to_image_database(self, filepath, strict=False, redacted=False):
        if self.image_client.check_image_db_if_filepath_imported(self.collection_name,filepath,exact=True):
            self.logger.info(f"Full filepath already imported: {filepath}")
            # return the reference here, see the redef of check_image_db_if_filepath_imported
            return False
        filename, filename_ext = self.split_filepath(filepath)

        if strict and self.image_client.check_image_db_if_filename_imported(filename, exact=True):
            self.logger.info(f"filename already imported: {filename}")
            # return the reference here
            return False
        deleteme = self.convert_if_required(filepath)
        if deleteme is not None:
            upload_me = deleteme
        else:
            upload_me = filepath.full_path

        self.logger.debug(
            f"about to import to client:- {redacted}, {upload_me}, {self.collection_name}, {upload_me}")

        url, attach_loc = self.image_client.upload_to_image_server(upload_me,
                                                                   redacted,
                                                                   self.collection_name,
                                                                   filepath)
        if deleteme is not None:
            os.remove(deleteme)
        return (url, attach_loc)

    def process_id(self, filepath_list, collection_object_id, agent_id, skeleton=False, copyright_map=None):
        # if dedupe_files:
        #     unique_filenames = {}
        #
        # for cur_filepath, cur_file_base, cur_file_ext in filepath_list:
        #     unique_filenames[cur_file_base] = None
        # for unique_filename in unique_filenames.keys():
        for cur_filepath in filepath_list:

            if self.image_client.check_image_db_if_filename_imported(cur_file_base + ".jpg", exact=True):
                self.logger.info(f"  Abort; already uploaded {cur_filepath}")
                continue

            for cur_filepath, cur_file_base, cur_file_ext in filepath_list:

                is_redacted = False
                if not skeleton:
                    is_redacted = self.attachment_utils.get_is_collection_object_redacted(collection_object_id)

                else:
                    is_redacted = True
                (url, attach_loc) = self.upload_filepath_to_image_database(cur_filepath, redacted=is_redacted)

            try:

                copyright = None
                if copyright_map is not None:
                    if cur_filepath.full_path in copyright_map:
                        copyright = copyright_map[cur_filepath.full_path]
                self.import_to_specify_database(cur_filepath.full_path,
                                                attach_loc,
                                                url,
                                                collection_object_id,
                                                agent_id,
                                                copyright=copyright)
            except Exception as e:
                self.logger.debug(
                    f"Upload failure to image server for file: \n\t{cur_filepath.full_path} \n\t{jpg_found}: \n\t{original_full_path}")
                self.logger.debug(f"Exception: {e}")
