#!/usr/bin/env python

from subprocess import Popen, PIPE, CalledProcessError
import sys
from mutagen.flac import FLAC
from mutagen.id3 import ID3, APIC, RVA2, TALB, TBPM, TCMP, TCOM, TCON, TCOP, TDOR, TDRC, TENC, TEXT, TIPL, TIT1, TIT2, TIT3, TLAN, TMCL, TMED, TMOO, TPE1, TPE2, TPE3, TPE4, TPOS, TPUB, TRCK, TSOA, TSOP, TSOT, TSRC, TSST, TXXX, UFID

def transcode(flac_filename, mp3_filename, bitrate=320):
    decoder_cmd = ['flac', '--decode', '--stdout', '--silent', flac_filename]
    encoder_cmd = ['lame', '-b', str(bitrate), '-h', '--silent', '-', mp3_filename]
    decoder = Popen(decoder_cmd, stdout=PIPE)
    encoder = Popen(encoder_cmd, stdin=decoder.stdout, stdout=PIPE)
    decoder.stdout.close() # allow decoder to receive SIGPIPE if encoder exits
    encoder.communicate()
    decoder.wait()
    if encoder.returncode != 0:
        raise CalledProcessError(encoder.returncode, ' '.join(encoder_cmd))
    if decoder.returncode != 0:
        raise CalledProcessError(decoder.returncode, ' '.join(decoder_cmd))

tag_map = {
    "album"        : TALB,
    "bpm"          : TBPM,
    "compilation"  : TCMP,
    "composer"     : TCOM,
    "genre"        : TCON,
    "copyright"    : TCOP,
    "originaldate" : TDOR,
    "date"         : TDRC,
    "encodeby"     : TENC,
    "lyricist"     : TEXT,
    "grouping"     : TIT1,
    "title"        : TIT2,
    "subtitle"     : TIT3,
    "language"     : TLAN,
    "media"        : TMED,
    "mood"         : TMOO,
    "artist"       : TPE1,
    "albumartist"  : TPE2,
    "conductor"    : TPE3,
    "remixer"      : TPE4,
    "label"        : TPUB,
    "albumsort"    : TSOA,
    "artistsort"   : TSOP,
    "titlesort"    : TSOT,
    "isrc"         : TSRC,
    "discsubtitle" : TSST,
    }

text_tag_map = {
    "catalognumber"              : u'CATALOGNUMBER',
    "barcode"                    : u'BARCODE',
    "musicbrainz_albumid"        : u"MusicBrainz Album Id",
    "musicbrainz_artistid"       : u"MusicBrainz Artist Id",
    "musicbrainz_albumartistid"  : u"MusicBrainz Album Artist Id",
    "musicbrainz_trmid"          : u"MusicBrainz TRM Id",
    "musicbrainz_discid"         : u"MusicBrainz Disc Id",
    "musicip_puid"               : u"MusicIP PUID",
    "releasestatus"              : u"MusicBrainz Album Status",
    "releasetype"                : u"MusicBrainz Album Type",
    "releasecountry"             : u"MusicBrainz Album Release Country",
    "asin"                       : u'ASIN',
    "script"                     : u'SCRIPT',
    "musicbrainz_releasegroupid" : u"MusicBrainz Release Group Id",
    "musicbrainz_workid"         : u"MusicBrainz Work Id",
    "albumartistsort"            : u'ALBUMARTISTSORT',
    }

def total(flac, total_tags):
    for tag in total_tags:
        if tag in flac:
            return u'/' + flac[tag][0]
    return u''

def replaygain(flac, id3, gain_type):
    gain_tag = 'replaygain_%s_gain' % gain_type
    peak_tag = 'replaygain_%s_peak' % gain_type
    if gain_tag in flac and peak_tag in flac:
        gain = float(flac[gain_tag][0][:-3])
        peak = float(flac[peak_tag][0][:-3])
        id3.add(RVA2(unicode(gain_type), 1, gain, peak))

def performers(people):
    return [x.rstrip(u')').rsplit(u' (', 1) for x in people]

def tag(flac_filename, mp3_filename):
    flac = FLAC(flac_filename)
    id3 = ID3()
    for tag, value in flac.iteritems():
        if tag in tag_map:
            id3.add(tag_map[tag](encoding=3, text=value))
        elif tag in text_tag_map:
            id3.add(TXXX(encoding=3, desc=text_tag_map[tag], text=value))
        elif tag == 'tracknumber':
            value[0] += total(flac, ['tracktotal', 'totaltracks'])
            id3.add(TRCK(encoding=3, text=value))
        elif tag == 'discnumber':
            value[0] += total(flac, ['disctotal', 'totaldiscs'])
            id3.add(TPOS(encoding=3, text=value))
        elif tag == 'musicbrainz_trackid':
            id3.add(UFID(u'http://musicbrainz.org', flac['musicbrainz_trackid']))
        elif tag == 'producer':
            id3.add(TIPL(encoding=3, people=[u'producer', value]))
        elif tag == 'performer':
            id3.add(TMCL(encoding=3, people=performers(value)))
        elif tag not in ['tracktotal', 'totaltracks', 'disctotal', 'totaldiscs', 'replaygain_album_gain', 'replaygain_album_peak', 'replaygain_track_gain', 'replaygain_track_peak']:
            print "Unknown tag %s=%s" % (tag, value)

    replaygain(flac, id3, 'album')
    replaygain(flac, id3, 'track')

    for pic in flac.pictures:
        tag = APIC(encoding=3, mime=pic.mime, type=pic.type, desc=pic.desc, data=pic.data)
        id3.add(tag)

    id3.save(mp3_filename)

def main():
    flac_filename = sys.argv[1]
    mp3_filename = sys.argv[2]
    transcode(flac_filename, mp3_filename)
    tag(flac_filename, mp3_filename)

if __name__ == '__main__':
    main()



