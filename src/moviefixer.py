#!/usr/bin/env python3
# # utf-8
import sys
import abc
import subprocess
import re
from enum import Enum, auto
import argparse
from pathlib import Path
import datetime
import configparser
import readline

RED   = "\033[1;31m"  
BLUE  = "\033[1;34m"
CYAN  = "\033[1;36m"
GREEN = "\033[0;32m"
RESET = "\033[0;0m"
BOLD    = "\033[;1m"
REVERSE = "\033[;7m"

class LanguageId(Enum):
    UNKNOWN = auto()
    ENGLISH = auto()
    FRENCH = auto()
    JAPANESE = auto()
    KOREAN = auto()
    SPANISH = auto()

class LanguageDef:

    def __init__(self, language_id, language_name, language_iso):
        """
        :param LanguageId language_id:
        :param str language_name:
        :param str language_iso: iso 639-2/T
        """
        self.language_id = language_id
        self.language_name = language_name
        self.language_iso = language_iso

class LanguageDefs:

    def __init__(self):
        self.language_defs = {}
        self.register_language_def(LanguageDef(LanguageId.UNKNOWN, 'Unknown', 'und'))
        self.register_language_def(LanguageDef(LanguageId.ENGLISH, 'English', 'eng'))
        self.register_language_def(LanguageDef(LanguageId.FRENCH, 'Francais', 'fra'))
        self.register_language_def(LanguageDef(LanguageId.JAPANESE, 'Japanese', 'jpn'))
        self.register_language_def(LanguageDef(LanguageId.KOREAN, 'Korean', 'kor'))
        self.register_language_def(LanguageDef(LanguageId.SPANISH, 'Espanol', 'spa'))
    
    def register_language_def(self, language_def):
        """
        :param LanguageDef language_def:
        """
        self.language_defs[language_def.language_id] = language_def

    def language_iso_to_id(self, language_iso):
        for language_def in self.language_defs.values():
            if language_def.language_iso == language_iso:
                return language_def.language_id

    def language_name_to_id(self, language_name):
        for language_def in self.language_defs.values():
            if language_def.language_name == language_name:
                return language_def.language_id

    def language_id_to_iso(self, language_id):
        return self.language_defs[language_id].language_iso

    def language_id_to_name(self, language_id):
        return self.language_defs[language_id].language_name

    def isos(self):
        return [language_def.language_iso for language_def in self.language_defs.values()]

    def names(self):
        return [language_def.language_name for language_def in self.language_defs.values()]

LANGUAGE_DEFS = LanguageDefs()

class Language:
    # we use iso 639-2/T codes https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes

    def __init__(self, language_id=None, language_name=None, language_iso=None):
        global LANGUAGE_DEFS
        if language_id is not None:
            assert language_name is None and language_iso is None
            self.language_id = language_id
        if language_name is not None:
            assert language_id is None and language_iso is None
            self.language_id = LANGUAGE_DEFS.language_name_to_id(language_name)
        if language_iso is not None:
            assert language_id is None and language_name is None
            self.language_id = LANGUAGE_DEFS.language_iso_to_id(language_iso)

    def __str__(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_iso(self.language_id)

    def __repr__(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_iso(self.language_id)
    
    @property
    def iso(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_iso(self.language_id)

    @property
    def name(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_name(self.language_id)

    @classmethod
    def names(cls):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.names()

    @classmethod
    def isos(cls):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.isos()


def execute_command(command):
    """
    :param list(str) command:
    :rtype int,str,str: 
    """
    # print('"'+'" "'.join([str(e) for e in command])+'"')
    completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #print(completed_process.stdout)
    #print(type(completed_process.stdout))
    return completed_process

def check_language_iso(iso_or_pseudo_iso):
    language_iso = iso_or_pseudo_iso
    norm = 'iso 639-2/T'
    if iso_or_pseudo_iso == 'fre':
        language_iso = 'fra'
        norm = 'iso 639-2/B'
    assert language_iso in Language.isos(), 'unexpected language iso : %s' % language_iso
    # https://medium.com/av-transcode/how-to-add-multiple-audio-tracks-to-a-single-video-using-ffmpeg-open-source-tool-27bff8cca30 :
    #   FFmpeg expects the language can be specified as an ISO 639–2/T or ISO 639–2/B (3 letters) code. ISO 639 is a set of international standards that lists shortcodes for language names.
    allowed_norms = ['iso 639-2/T', 'iso 639-2/B']  # not sure which norms are actually allowed
    if norm not in allowed_norms:
        print(RED, 'warning : %s is not in the norm %s, which is not the allowed norms %s language code; replaced with %s' % (iso_or_pseudo_iso, norm, allowed_norms, language_iso), RESET)
    return language_iso

def check_language_name(name_or_pseudo_name):
    language_name = name_or_pseudo_name
    #if language_name == 'Francais':
    #    language_name = 'French'
    assert language_name in Language.names(), 'unexpected language name : %s' % language_name
    if name_or_pseudo_name != language_name:
        print(RED, 'warning : %s is not an expected language name; replaced with %s' % (name_or_pseudo_name, language_name), RESET)
    return language_name


def _find_audio_tracks_defs(ffprobe_stderr):
    # avi movie files can't store audio track language information in the audiostreams themselves. Instead, these information is stored as riff tags in the header of the file.
    # search for audiotrack language information from header (in IAS<n> riff tags)
    # https://exiftool.org/TagNames/RIFF.html
    # https://wiki.multimedia.cx/index.php/FFmpeg_Metadata
    stream_language_defs = {}
    header_language_defs = {}

    for line in ffprobe_stderr.split(b'\n'):
        # print('stderr' + line)
        # match = re.match('^\s*IAS1\s+:\s*[a-zA-Z]+\s+$', line)
        try:
            line_as_str = str(line, encoding='utf-8')
        except UnicodeDecodeError as e:  # pylint: disable=unused-variable
            line_as_str = str(line, encoding='latin_1')
        #     IAS1            : English
        #     IAS1            : Japanese
        #     IAS1            : Francais
        match = re.match(r'^\s*IAS([0-9]+)\s+:\s*([a-zA-Z]+)\s*$', line_as_str)
        if match:
            audio_stream_def = {}
            track_index = int(match.groups()[0]) - 1
            assert track_index >= 0
            audio_stream_def['audio_track_id'] = track_index
            language_name = check_language_name(match.groups()[1])
            language_iso = Language(language_name=language_name).iso
            audio_stream_def['language_iso'] = language_iso
            audio_stream_def['from_header'] = 'IAS%s:%s' % (match.groups()[0], match.groups()[1])
            # if match.groups()[1] not in ['und']:
            #    print(match.groups()[1])
            header_language_defs[track_index] = audio_stream_def

        # for avi files :
        # Stream #0:1: Audio: mp3 (U[0][0][0] / 0x0055), 48000 Hz, stereo, s16p, 138 kb/s

        # for mp4 files :
        # Stream #0:0(und): Video: mpeg4 (mp4v / 0x7634706D), yuv420p, 576x432 [SAR 1:1 DAR 4:3], 1002 kb/s, 23.98 fps, 23.98 tbr, 24k tbn, 2 tbc (default)
        # Metadata:
        #   handler_name    : VideoHandler
        # Stream #0:1(jpn): Audio: mp3 (mp4a / 0x6134706D), 44100 Hz, mono, s16p, 96 kb/s (default)
        # Metadata:
        #   handler_name    : SoundHandler

        # print(line_as_str)
        match = re.match(r'^\s*Stream #([0-9]+):([0-9]+)([^\:]*): Audio:\s', line_as_str)
        if match:
            audio_stream_def = {}
            audio_stream_def['majorid'] = match.groups()[0]
            audio_stream_def['minorid'] = match.groups()[1]
            stream_id = '%s:%s' % (audio_stream_def['majorid'], audio_stream_def['minorid'])
            audio_stream_def['stream_id'] = stream_id

            language_substring = match.groups()[2]  # it is expected to look loke "(jpn)"
            if language_substring != '':
                # the language of the audio stream is defined
                match = re.match(r'^\(([a-z]+)\)$', language_substring)
                assert match, "unexpected case : '%s' is expected to be of the form '(<language-iso-639-code>)' " % language_substring
                
                audio_stream_def['language_iso'] = check_language_iso(match.groups()[0])
                audio_stream_def['from_stream'] = '%s' % match.groups()[0]
            else:
                audio_stream_def['language_iso'] = ''
                audio_stream_def['from_stream'] = ''
            stream_language_defs[stream_id] = audio_stream_def

    # print(header_language_defs)
    # print(stream_language_defs)
    assert len(header_language_defs) <= len(stream_language_defs), "the number of audio streams found in the header (%d) don't match the actual number of audio streams (%d)" % (len(header_language_defs), len(stream_language_defs))

    # sorted_track_ids = sorted([ audio_stream_def['stream_id'] for audio_stream_def in stream_language_defs.values() ])
    sorted_track_ids = sorted(stream_language_defs.keys())
    # print(sorted_track_ids)

    for audio_stream_def in header_language_defs.values():
        assert audio_stream_def['audio_track_id'] < len(stream_language_defs), "audio_stream_def %s 's references a non-existing stream index (%d)" % (str(audio_stream_def), audio_stream_def['audio_track_id'])


    for track_index in range(len(sorted_track_ids)):
        track_id = sorted_track_ids[track_index]
        audio_stream_def = stream_language_defs[track_id]
        if track_index in header_language_defs.keys():
            audio_stream_def['from_header'] = header_language_defs[track_index]['from_header']
            if audio_stream_def['language_iso'] == '':
                audio_stream_def['language_iso'] = header_language_defs[track_index]['language_iso']
            else:
                assert audio_stream_def['language_iso'] == header_language_defs[track_index]['language_iso']
        if audio_stream_def['language_iso'] == '':
            audio_stream_def['language_iso'] = 'und'

    return stream_language_defs



def get_movie_title(movie_file_path):
    """
    :param Path movie_file_path:
    :rtype str:
    """
    assert isinstance(movie_file_path, Path)
    title = ''
    completed_process = execute_command(['ffprobe', movie_file_path.expanduser()])
    assert completed_process.returncode == 0, completed_process.stderr
    ffprobe_stderr = completed_process.stderr
    for line in ffprobe_stderr.split(b'\n'):
        try:
            line_as_str = str(line, encoding='utf-8')
        except UnicodeDecodeError as e:  # pylint: disable=unused-variable
            line_as_str = str(line, encoding='latin_1')
        match = re.match(r'^\s*title\s+: (.+)$', line_as_str)
        if match:
            title = match.groups()[0]
    return title

def get_movie_track_languages(movie_file_path):
    """
    :param Path movie_file_path:
    :rtype list(Language):
    """
    assert isinstance(movie_file_path, Path)
    # print(movie_file_path)
    languages = []
    completed_process = execute_command(['ffprobe', movie_file_path.expanduser(), '-show_entries', 'stream_tags=language'])
    assert completed_process.returncode == 0, completed_process.stderr
    ffprobe_stderr = completed_process.stderr
    header_language_defs = _find_audio_tracks_defs(ffprobe_stderr)
    for audio_stream_def in header_language_defs.values():
        # print(audio_stream_def)
        languages.append(Language(language_iso=audio_stream_def['language_iso']))

    return languages


class MovieContainerType(Enum):
    AVI = auto()
    MP4 = auto()
    MKV = auto()


def get_movie_container_type(movie_file_path):
    suffix = movie_file_path.suffix
    if suffix in ['.avi']:
        return MovieContainerType.AVI
    if suffix in ['.mp4']:
        return MovieContainerType.MP4
    if suffix in ['.mkv']:
        return MovieContainerType.MKV
    assert False, 'unexpected suffix : %s' % suffix
    

def create_backup(file_path):
    """
    :param Path file_path:
    """
    assert isinstance(file_path, Path)
    now_date = datetime.datetime.now()
    backup_file_path = file_path.with_name(file_path.stem + '.asof_' + now_date.strftime("%Y_%m_%d_%H_%M_%S")  + file_path.suffix)
    # backup_file_path = Path('/tmp/' + file_path.stem + '.asof_' + now_date.strftime("%Y_%m_%d_%H_%M_%S")  + file_path.suffix)
    # print(backup_file_path)
    completed_process = execute_command(['rsync', '-va', str(file_path.expanduser()), str(backup_file_path.expanduser())])
    assert completed_process.returncode == 0, completed_process.stderr

    return backup_file_path

# def read_movie_metadata(src_movie_file_path):
#     """
#     :param Path movie_file_path:
#     :rtype config:
#     """
#     ini_file_path = Path('/tmp/ffmetadata.ini')
#     command = []
#     command.append('ffmpeg')
#     command.append('-i')
#     command.append(src_movie_file_path.expanduser())
#     command.append('-f')
#     command.append('ffmetadata')
#     command.append(ini_file_path.expanduser())
#     completed_process = execute_command(command)
#     assert completed_process.returncode == 0, completed_process.stderr

#     config = configparser.ConfigParser()
#     config.read(ini_file_path.expanduser())
#     return config

class BackupMode(Enum):
    MODIFY_ORIGINAL=auto()
    MODIFY_BACKUP=auto()
    NO_BACKUP=auto()


class IMetadataModifier(abc.ABC):

    @abc.abstractmethod
    def movie_is_suitable(self, src_movie_file_path):
        pass

    @abc.abstractmethod
    def get_ffmpeg_options(self, src_movie_file_path):
        """
        :rtype list(str): the list of ffmpeg options to perfrom the change
        """
        pass

    @abc.abstractmethod
    def check_modified_movie(self, dst_movie_file_path):
        pass

class TracksLanguageModifier(IMetadataModifier):

    def __init__(self, languages):
        """
        :param list(Language) language:
        """
        self.languages = languages

    def movie_is_suitable(self, src_movie_file_path):
        audio_track_languages = get_movie_track_languages(src_movie_file_path)
        # print("existing track defs: ", audio_track_languages)
        if len(audio_track_languages) != len(self.languages):
            return False, "unexpected number of languages in %s (%d languages are expected) " % (str(self.languages), len(audio_track_languages))
        return True, ""

    def get_ffmpeg_options(self, src_movie_file_path):
        for track_index in range(len(self.languages)):
            ffmpeg_options = []
            # track_id = sorted_track_ids[track_index]
            if get_movie_container_type(src_movie_file_path) == MovieContainerType.AVI:
                # print('avi')
                # find a way to set riff IAS1 to the language
                # https://superuser.com/questions/783895/ffmpeg-edit-avi-metadata-and-audio-track-naming
                #     Took quite a long time for me to figure this out. I'm posting it here, because even after 3 years this thread is one of the first hits in google search: AVI (more specific: RIFF) does support language names but in opposite to mkv, the metadata is not stored in the stream but in the header using tags IAS1-9 for up to 9 different audio streams.
                #  
                #     ffmpeg -i input.avi -map 0 -codec copy -metadata IAS1=eng -metadata IAS2=ger output.avi
                #
                #     VLC ist pretty tolerant. If you enter ISO code "ger", VLC translates it to "Deutsch", if you enter "MyLang" instead, VLC displays "MyLang". Other software like Kodi needs the the correct ISO code. It would read "MyL" only and then display the language as unknown.
                #
                #     However, please be aware that ffmpeg does not just add the language but also changes other metadata. For example, audio interleave and preload data are different in output.avi, no idea if this is good or might result in audio out of sync. Check with MediaInfo or similar.


                # https://exiftool.org/TagNames/RIFF.html
                ffmpeg_options.append('-metadata')
                ffmpeg_options.append('IAS%d=%s' % (track_index + 1, self.languages[track_index].name))
            else:
                # print('not avi')
                ffmpeg_options.append('-metadata:s:a:%s' % track_index)
                ffmpeg_options.append('language=%s' % self.languages[track_index].iso)
        return ffmpeg_options

    def check_modified_movie(self, dst_movie_file_path):
        dst_audio_track_languages = get_movie_track_languages(dst_movie_file_path)
        if [l.iso for l in self.languages] != [l.iso for l in dst_audio_track_languages]:
            return False, '%s <> %s' % (str(self.languages), str(dst_audio_track_languages))
        return True, ""


class ITitleGuesser(abc.ABC):

    @abc.abstractmethod
    def guess_title(self, file_path):
        pass


class TitleFromFileName(ITitleGuesser):

    def __init__(self, filename_reg_exp=r'^(?P<year>[0-9]+) - (?P<title>[^\[.]+)'):
        """
        :param str filename_reg_exp: python style regular expression with in which it is expected to find a group named title. This group named 'title' is used to find the title of the movie in the file's name
        """
        assert re.search(r'\?P<title>', filename_reg_exp), "regular expression %s is expected to have a group named 'title'" % (filename_reg_exp)
        self.filename_reg_exp = filename_reg_exp

    def guess_title(self, file_path):
        title = None
        print(file_path.stem)
        match = re.match(self.filename_reg_exp, file_path.stem)
        if match:
            if 'title' in match.groupdict():
                title = match.groupdict()['title']
        return title

class TitleModifier(IMetadataModifier):

    def __init__(self, new_title):
        """
        :param str new_title:
        """
        self.new_title = new_title

    def movie_is_suitable(self, src_movie_file_path):
        return True, ""

    def get_ffmpeg_options(self, src_movie_file_path):
        ffmpeg_options = []
        ffmpeg_options.append('-metadata')
        ffmpeg_options.append('title=%s' % self.new_title)
        return ffmpeg_options

    def check_modified_movie(self, dst_movie_file_path):
        return True, ""

def modify_movie_metadata(movie_file_path, modifiers):
    """
    :param Path movie_file_path:
    :param list(IMetadataModifier) modifiers:
    """
    assert isinstance(movie_file_path, Path)

    for modifier in modifiers:
        is_suitable, error_message = modifier.movie_is_suitable(movie_file_path)
        if not is_suitable:
            assert False, error_message

    backup_mode = BackupMode.MODIFY_ORIGINAL

    movie_backup_file_path = create_backup(movie_file_path)

    if backup_mode == BackupMode.MODIFY_BACKUP:
        src_movie_file_path = movie_file_path
        dst_movie_file_path = movie_backup_file_path
    elif backup_mode in [BackupMode.MODIFY_ORIGINAL, BackupMode.NO_BACKUP]:
        src_movie_file_path = movie_backup_file_path
        dst_movie_file_path = movie_file_path
    else:
        assert False
    # sorted_track_ids = sorted(audio_track_languages.keys())
    command = []
    command.append('ffmpeg')
    command.append('-y')
    command.append('-i')
    command.append(src_movie_file_path.expanduser())

    # https://stackoverflow.com/questions/37820083/ffmpeg-not-copying-all-audio-streams
    # FFmpeg have option to map all streams to output, you have to use option -map 0 to map all streams from input to output.
    command.append('-c')
    command.append('copy')
    command.append('-map')
    command.append('0')

    for modifier in modifiers:
        command += modifier.get_ffmpeg_options(movie_file_path)

    command.append(dst_movie_file_path.expanduser())

    # ffmpeg -i input.mp4 -map 0 -codec copy -metadata:s:a:0 language=eng -metadata:s:a:1 language=rus output.mp4
    completed_process = execute_command(command)
    assert completed_process.returncode == 0, completed_process.stderr

    check_result = True
    if check_result:
        for modifier in modifiers:
            modification_succeeded, error_message = modifier.check_modified_movie(dst_movie_file_path)
            if not modification_succeeded:
                assert False, error_message


        src_file_size = src_movie_file_path.stat().st_size
        dst_file_size = dst_movie_file_path.stat().st_size
        # print(src_file_size, dst_file_size)
        assert 0.99 < float(dst_file_size)/float(src_file_size) < 1.02
        # assert abs(src_file_size - dst_file_size) < 1000

        # src_metadata = read_movie_metadata(src_movie_file_path)
        # dst_metadata = read_movie_metadata(dst_movie_file_path)

    if backup_mode == BackupMode.NO_BACKUP:
        # delete the backup
        src_movie_file_path.unlink()


def fix_movie_file(movie_file_path):
    languages = get_movie_track_languages(movie_file_path)
    print(languages)

_input = input
def input(prompt, initial=''):
    readline.set_startup_hook(lambda: readline.insert_text(initial))
    try:
        return _input(prompt)
    finally:
        readline.set_startup_hook(None)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='edit metadata inside movie files')
    subparsers = parser.add_subparsers()
    subparsers.required = True
    subparsers.dest = 'command'

    show_audio_language_subparser = subparsers.add_parser("show-audio-languages", help="shows the audio track languages of the given video files")
    show_audio_language_subparser.add_argument('movie_file_path', nargs='+')

    set_audio_language_subparser = subparsers.add_parser("set-audio-language", help="sets the audio track language of the given video file")
    set_audio_language_subparser.add_argument('--languages', required=True, choices=LANGUAGE_DEFS.isos(), nargs='+')
    set_audio_language_subparser.add_argument('--movie-file-path', required=True)

    modify_metadata_subparser = subparsers.add_parser("modify-metadata", help="allows the user to interactively modify metadata")
    modify_metadata_subparser.add_argument('-l', '--fix-undefined-audio-languages', required=False, action='store_true', help="define the undefined language of audiotracks")
    modify_metadata_subparser.add_argument('-t', '--fix-title', required=False, action='store_true', help="define the title")
    modify_metadata_subparser.add_argument('-m', '--movie-file-path', required=True, nargs='+')
    modify_metadata_subparser.add_argument('-g', '--add-title-guesser', required=False, action='append', dest='title_guessers', help="add a title guesser which guesses the title from the filename obeying the given regular expression")
    namespace = parser.parse_args()
    # print(namespace)

    if namespace.command == 'show-audio-languages':
        for movie_file_path in namespace.movie_file_path:
            # print(movie_file_path)
            try:
                languages = get_movie_track_languages(Path(movie_file_path))
                print(Path(movie_file_path), BLUE, languages, RESET)
            except:
                print(RED, "failed to process %s" % movie_file_path, RESET)
                raise

    if namespace.command == 'set-audio-language':
        tracks_language_modifier = TracksLanguageModifier([Language(language_iso=language_iso) for language_iso in namespace.languages ])
        modify_movie_metadata(Path(namespace.movie_file_path), modifiers=[tracks_language_modifier])

    if namespace.command == 'modify-metadata':
        print(namespace)
        title_guessers = []
        for title_guesser_arg_value in namespace.title_guessers:
            match = re.match('^(?P<type>[a-z_]+):(?P<arg>.*)$', title_guesser_arg_value)
            if not match:
                match = re.match('^(?P<type>[a-z_]+)$', title_guesser_arg_value)
            assert match, "bad argument value for title guesser '%s' : it is expecte to be of the form <guesser_type>:<guesser_args>" % title_guesser_arg_value
            if match['type'] == 'filename_re':
                filename_re = match['arg']
                title_guessers.append(TitleFromFileName(filename_re))
            else:
                assert False, "unexpected title guesser type : %s" % match['type']
        for movie_file_path in namespace.movie_file_path:
            print("%s%s%s :" % (BLUE, movie_file_path, RESET))
            metadata_modifiers = []
            if namespace.fix_undefined_audio_languages:
                old_audio_track_languages = get_movie_track_languages(Path(movie_file_path))
                print("Current track languages : %s" % (old_audio_track_languages))
                new_audio_track_languages = []
                for track_index in range(len(old_audio_track_languages)):
                    chosen_language_iso = old_audio_track_languages[track_index].iso
                    if old_audio_track_languages[track_index].iso == "und":
                        while True:
                            print("Choose a language for the undefined audiotrack #%d : " % track_index, end='', flush=True)
                            chosen_language_iso = sys.stdin.readline().rstrip()
                            if chosen_language_iso in Language.isos():
                                break
                            else:
                                print(RED, "unexpected language %s : valid values are %s" % (chosen_language_iso, Language.isos()), RESET)
                    new_audio_track_languages.append(Language(language_iso=chosen_language_iso))
                # print(old_audio_track_languages, new_audio_track_languages)
                if [l.iso for l in old_audio_track_languages] != [l.iso for l in new_audio_track_languages]:
                    tracks_language_modifier = TracksLanguageModifier(new_audio_track_languages)
                    print("%ssetting audio track languages to %s%s" % (GREEN, new_audio_track_languages, RESET))
                    metadata_modifiers.append(tracks_language_modifier)
            if namespace.fix_title:
                old_title = get_movie_title(Path(movie_file_path))
                guessed_title = None
                for title_guesser in title_guessers:
                    guessed_title = title_guesser.guess_title(Path(movie_file_path))
                    if guessed_title != None:
                        break
                if guessed_title == None:
                    guessed_title = old_title
                # print("Choose a title (old title : %s%s%s) : " % (CYAN, old_title, RESET), end='', flush=True)
                # chosen_title = sys.stdin.readline().rstrip()
                new_title = input("Choose a title (old title : %s'%s'%s) : " % (BOLD, old_title, RESET), guessed_title)
                if new_title != old_title:
                    print("%schanging title from '%s' to '%s'%s" % (GREEN, old_title, new_title, RESET))
                    metadata_modifiers.append(TitleModifier(new_title))
            if len(metadata_modifiers) != 0:
                modify_movie_metadata(Path(movie_file_path), metadata_modifiers)
