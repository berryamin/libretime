import os
import logging
import uuid
from boto.s3.connection import S3Connection
from boto.s3.key import Key

STORAGE_BACKEND_FILE = "file"

class CloudStorageUploader:
    """ A class that uses Python-Boto SDK to upload objects into Amazon S3.
    
    It is important to note that every file, coming from different Airtime Pro
    stations, will get uploaded into the same bucket on the same Amazon S3
    account.

    Attributes:
        _host: Host name for the specific region assigned to the bucket.
        _bucket: Name of container on Amazon S3 where files will get uploaded into.
        _api_key: Access key to objects on Amazon S3.
        _api_key_secret: Secret access key to objects on Amazon S3.
    """

    def __init__(self, config):

        CLOUD_STORAGE_CONFIG_SECTION = config.get("current_backend", "storage_backend")
        self._storage_backend = CLOUD_STORAGE_CONFIG_SECTION
        if self._storage_backend == STORAGE_BACKEND_FILE:
            self._host = ""
            self._bucket = ""
            self._api_key = ""
            self._api_key_secret = ""
        else:
            self._host = config.get(CLOUD_STORAGE_CONFIG_SECTION, 'host')
            self._bucket = config.get(CLOUD_STORAGE_CONFIG_SECTION, 'bucket')
            self._api_key = config.get(CLOUD_STORAGE_CONFIG_SECTION, 'api_key')
            self._api_key_secret = config.get(CLOUD_STORAGE_CONFIG_SECTION, 'api_key_secret')

    def enabled(self):
        if self._storage_backend == "file":
            return False
        else:
            return True


    def upload_obj(self, audio_file_path, metadata):
        """Uploads a file into Amazon S3 object storage.
        
        Before a file is uploaded onto Amazon S3 we generate a unique object
        name consisting of the filename and a unqiue string using the uuid4
        module.
        
        Keyword arguments:
            audio_file_path: Path on disk to the audio file that is about to be
                             uploaded to Amazon S3 object storage.
            metadata: ID3 tags and other metadata extracted from the audio file.
            
        Returns:
            The metadata dictionary it received with three new keys:
                filesize: The file's filesize in bytes.
                filename: The file's filename.
                resource_id: The unique object name used to identify the objects
                             on Amazon S3 
        """

        file_base_name = os.path.basename(audio_file_path)
        file_name, extension = os.path.splitext(file_base_name)
        
        # With Amazon S3 you cannot create a signed url if there are spaces 
        # in the object name. URL encoding the object name doesn't solve the
        # problem. As a solution we will replace spaces with dashes.
        file_name = file_name.replace(" ", "-")
        
        unique_id = str(uuid.uuid4())
        
        # We add another prefix to the resource name with the last two characters
        # of the unique id so files are not all placed under the root folder. We
        # do this in case we need to restore a customer's file/s; File restoration
        # is done via the S3 Browser client. The client will hang if there are too
        # many files under the same folder.
        unique_id_prefix = unique_id[-2:]
        
        resource_id = "%s/%s/%s_%s%s" % (metadata['file_prefix'], unique_id_prefix, file_name, unique_id, extension)

        conn = S3Connection(self._api_key, self._api_key_secret, host=self._host)
        bucket = conn.get_bucket(self._bucket)
        
        key = Key(bucket)
        key.key = resource_id
        key.set_metadata('filename', file_base_name)
        key.set_contents_from_filename(audio_file_path)

        metadata["filesize"] = os.path.getsize(audio_file_path)
        
        # Remove file from organize directory
        try:
            os.remove(audio_file_path)
        except OSError:
            logging.info("Could not remove %s from organize directory" % audio_file_path)
        
        # Pass original filename to Airtime so we can store it in the db
        metadata["filename"] = file_base_name
        
        metadata["resource_id"] = resource_id
        metadata["storage_backend"] = self._storage_backend
        return metadata

