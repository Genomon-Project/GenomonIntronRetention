#!/usr/bin/env python

"""
Simple python wrapper for SSW library
Please put the path of libssw.so into LD_LIBRARY_PATH or pass it explicitly as a parameter
By Yongan Zhao (March 2016)

Modified by Yuichi Shiraishi for python3 compatibility (May 2019)
"""

from __future__ import print_function

import sys, os, re
import os.path as op
import argparse as ap
import ctypes as ct
import timeit as ti
import gzip
import math

from . import ssw_lib

if sys.version_info.major == 2:
    range = xrange
    


def read(sFile):
    """
    read a sequence file
    @param  sFile   sequence file
    """
    def read_one_fasta(f):
        """
        read a fasta file
        @param  f   file handler
        """
        sId = ''
        sSeq = ''
        """
        for l in f:
            if l.startswith('>'):
                if sSeq:
                    yield sId, sSeq, ''
                sId = l.strip()[1:].split()[0]
                sSeq = ''
            else:
                sSeq += l.strip()
        """
        for line in f:
            if line.startswith('>'):
                if sSeq:
                    yield sId, sSeq, ''
                sId = line.rstrip('\n')[1:].split()[0]
                sSeq = ''
            else:
                sSeq += line

        """
        for l in f:
            if l.startswith('>'):
                if sSeq:
                    yield sId, sSeq, ''
                sId = l.strip()[1:].split()[0]
                sSeq = ''
            else:
                sSeq += l.strip()
        """

        yield sId, sSeq, ''

    def read_one_fastq(f):
        """
        read a fastq file
        @param  f   file handler
        """
        sId = ''
        sSeq = ''
        s3 = ''
        sQual = ''
        """
        for l in f:
            sId = l.strip()[1:].split()[0]
            sSeq = next(f)
            s3 = next(f)
            sQual = next(f)

            yield sId, sSeq, sQual
        """

        sId = f.readline()

        while sId:
            sId = sId.rstrip('\n').split()[0]
            sSeq = f.readline().rstrip('\n')
            line = f.readline().rstrip('\n')
            sQual = f.readline().rstrip('\n')
            yield sId, sSeq, sQual
            sId = f.readline()

        f.close()
        

# test if fasta or fastq
    bFasta = True
    ext = op.splitext(sFile)[1][1:].strip().lower()
    if ext == 'gz' or ext == 'gzip':
        with gzip.open(sFile, 'rt') as f:
            l = f.readline().rstrip('\n')
            # l = next(f)
            if l.startswith('>'):
                bFasta = True
            else:
                bFasta = False
            """
            elif l.startswith('@'):
                bFasta = False
            else:
                print('file format cannot be recognized', file = sys.stderr)
                sys.exit()
            """
    else:
        with open(sFile, 'r') as f:
            l = f.readline().rstrip('\n')
            # l = next(f)
            if l.startswith('>'):
                bFasta = True
            else:
                bFasta = False
            """
            elif l.startswith('@'):
                bFasta = False
            else:
                print('file format cannot be recognized', file = sys.stderr)
                sys.exit()
            """
# read
    if ext == 'gz' or ext == 'gzip':
        with gzip.open(sFile, 'r') as f:
            if bFasta == True:
                for sId,sSeq,sQual in read_one_fasta(f):
                    yield sId, sSeq, sQual
            else:
                for sId,sSeq,sQual in read_one_fastq(f):
                    yield sId, sSeq, sQual
    else:
        with open(sFile, 'r') as f:
            if bFasta == True:
                for sId,sSeq,sQual in read_one_fasta(f):
                    yield sId, sSeq, sQual
            else:
                for sId,sSeq,sQual in read_one_fastq(f):
                    yield sId, sSeq, sQual


def to_int(seq, lEle, dEle2Int):
    """
    translate a sequence into numbers
    @param  seq   a sequence
    """
    num_decl = len(seq) * ct.c_int8
    num = num_decl()
    for i,ele in enumerate(seq):
        try:
            n = dEle2Int[ele]
        except KeyError:
            n = dEle2Int[lEle[-1]]
        finally:
            num[i] = n

    return num


def align_one(ssw, qProfile, rNum, nRLen, nOpen, nExt, nFlag, nMaskLen):
    """
    align one pair of sequences
    @param  qProfile   query profile
    @param  rNum   number array for reference
    @param  nRLen   length of reference sequence
    @param  nFlag   alignment flag
    @param  nMaskLen   mask length
    """
    res = ssw.ssw_align(qProfile, rNum, ct.c_int32(nRLen), nOpen, nExt, nFlag, 0, 0, nMaskLen)

    nScore = res.contents.nScore
    nScore2 = res.contents.nScore2
    nRefBeg = res.contents.nRefBeg
    nRefEnd = res.contents.nRefEnd
    nQryBeg = res.contents.nQryBeg
    nQryEnd = res.contents.nQryEnd
    nRefEnd2 = res.contents.nRefEnd2
    lCigar = [res.contents.sCigar[idx] for idx in range(res.contents.nCigarLen)]
    nCigarLen = res.contents.nCigarLen
    ssw.align_destroy(res)

    return (nScore, nScore2, nRefBeg, nRefEnd, nQryBeg, nQryEnd, nRefEnd2, nCigarLen, lCigar)


def buildPath(q, r, nQryBeg, nRefBeg, lCigar):
    """
    build cigar string and align path based on cigar array returned by ssw_align
    @param  q   query sequence
    @param  r   reference sequence
    @param  nQryBeg   begin position of query sequence
    @param  nRefBeg   begin position of reference sequence
    @param  lCigar   cigar array
    """
    sCigarInfo = 'MIDNSHP=X'
    sCigar = ''
    sQ = ''
    sA = ''
    sR = ''
    nQOff = nQryBeg
    nROff = nRefBeg
    for x in lCigar:
        n = x >> 4
        m = x & 15
        if m > 8:
            c = 'M'
        else:
            c = sCigarInfo[m]
        sCigar += str(n) + c

        if c == 'M':
            sQ += q[nQOff : nQOff+n]
            sA += ''.join(['|' if q[nQOff+j] == r[nROff+j] else '*' for j in range(n)])
            sR += r[nROff : nROff+n]
            nQOff += n
            nROff += n
        elif c == 'I':
            sQ += q[nQOff : nQOff+n]
            sA += ' ' * n
            sR += '-' * n
            nQOff += n
        elif c == 'D':
            sQ += '-' * n
            sA += ' ' * n
            sR += r[nROff : nROff+n]
            nROff += n

    return sCigar, sQ, sA, sR




def main(args):
    lEle = []
    dRc = {} 
    dEle2Int = {}
    dInt2Ele = {}
    if False == args.bProtien:
# init DNA score matrix
        if not args.sMatrix:
            lEle = ['A', 'C', 'G', 'T', 'N']
            dRc = {'A':'C', 'C':'G', 'G':'C', 'T':'A', 'a':'C', 'c':'G', 'g':'C', 't':'A'} 
            for i,ele in enumerate(lEle):
                dEle2Int[ele] = i
                dEle2Int[ele.lower()] = i
                dInt2Ele[i] = ele
            nEleNum = len(lEle)
            lScore = [0 for i in range(nEleNum**2)]
            for i in range(nEleNum-1):
                for j in range(nEleNum-1):
                    if lEle[i] == lEle[j]:
                        lScore[i*nEleNum+j] = args.nMatch
                    else:
                        lScore[i*nEleNum+j] = -args.nMismatch
        else:
            lEle, dEle2Int, dInt2Ele, lScore = ssw.read_matrix(args.sMatrix)
    else:
# load AA score matrix
        if not args.sMatrix:
            lEle = 'A   R   N   D   C   Q   E   G   H   I   L   K   M   F   P   S   T   W   Y   V   B   Z   X   *'.split()
            for i,ele in enumerate(lEle):
                dEle2Int[ele] = i
                dEle2Int[ele.lower()] = i
                dInt2Ele[i] = ele
            nEleNum = len(lEle)
            lScore = ssw_lib.lBlosum50
        else:
            # assume the format of the input score matrix is the same as that of http://www.ncbi.nlm.nih.gov/Class/FieldGuide/BLOSUM62.txt
            lEle, dEle2Int, dInt2Ele, lScore = ssw.read_matrix(args.sMatrix)

    if args.bBest and args.bProtien:
        print('Reverse complement alignment is not available for protein sequences.', file = sys.stderr)

# translate score matrix to ctypes
    mat = (len(lScore) * ct.c_int8) ()
    mat[:] = lScore
# set flag
    nFlag = 0
    if args.bPath:
        nFlag = 2
# print sam head
    if args.bSam and args.bHeader and args.bPath:
        print('@HD\tVN:1.4\tSO:queryname')
        for sRId,sRSeq,_ in read(sTarget):
            print('@SQ\tSN:{}\tLN:{}'.format(sRId, len(sRSeq)))
    elif args.bSam and not args.bPath:
        print('SAM format output is only available together with option -c.\n', file = sys.stderr)
        args.bSam = False

    ssw = ssw_lib.CSsw(args.sLibPath)
# iterate query sequence
    for sQId,sQSeq,sQQual in read(args.query):
# build query profile
        qNum = to_int(sQSeq, lEle, dEle2Int)
        qProfile = ssw.ssw_init(qNum, ct.c_int32(len(sQSeq)), mat, len(lEle), 2)
# build rc query profile
        if args.bBest and not args.bProtien:
            sQRcSeq = ''.join([dRc[x] for x in sQSeq[::-1]])
            qRcNum = to_int(sQRcSeq, lEle, dEle2Int)
            qRcProfile = ssw.ssw_init(qRcNum, ct.c_int32(len(sQSeq)), mat, len(lEle), 2)
# set mask len
        if len(sQSeq) > 30:
            nMaskLen = int(len(sQSeq) / 2)
        else:
            nMaskLen = 15

# iter target sequence
        for sRId,sRSeq,_ in read(args.target):
            rNum = to_int(sRSeq, lEle, dEle2Int)

# format ofres: (nScore, nScore2, nRefBeg, nRefEnd, nQryBeg, nQryEnd, nRefEnd2, nCigarLen, lCigar)
            res = align_one(ssw, qProfile, rNum, len(sRSeq), args.nOpen, args.nExt, nFlag, nMaskLen)
# align rc query
            resRc = None
            if args.bBest and not args.bProtien:
                resRc = align_one(ssw, qRcProfile, rNum, len(sRSeq), args.nOpen, args.nExt, nFlag, nMaskLen)

# build cigar and trace back path
            strand = 0
            if resRc == None or res[0] > resRc[0]:
                resPrint = res
                strand = 0
                sCigar, sQ, sA, sR = buildPath(sQSeq, sRSeq, res[4], res[2], res[8])
            else:
                resPrint = resRc
                strand = 1
                sCigar, sQ, sA, sR = buildPath(sQRcSeq, sRSeq, resRc[4], resRc[2], resRc[8])

            print('\t'.join([sQId, sRId, sCigar, sQ, sA, sR]))
            print(sQ)
            print(sA)
            print(sR)
            print(res)

# print results
            if not args.bSam:
                print('target_name: {}\nquery_name: {}\noptimal_alignment_score: {}\t'.format(sRId, sQId, resPrint[0]), end = '')
                if resPrint[1] > 0:
                    print('suboptimal_alignment_score: {}\t'.format(resPrint[1]), end = '')
                if strand == 0:
                    print('strand: +\t', end = '')
                else: 
                    print('strand: -\t', end = '')
                if resPrint[2] + 1:
                    print('target_begin: {}\t'.format(resPrint[2] + 1), end = '')
                print('target_end: {}\t'.format(resPrint[3] + 1), end = '')
                if resPrint[4] + 1:
                    print('query_begin: {}\t'.format(resPrint[4] + 1), end = '')
                print('query_end: {}\n'.format(resPrint[5] + 1))
                if resPrint[-2] > 0:
                    n1 = 1 + resPrint[2]
                    n2 = min(60,len(sR)) + resPrint[2] - sR.count('-',0,60)
                    n3 = 1 + resPrint[4]
                    n4 = min(60,len(sQ)) + resPrint[4] - sQ.count('-',0,60)
                    for i in range(0, len(sQ), 60):
                        print('Target:{:>8}\t{}\t{}'.format(n1, sR[i:i+60], n2))
                        n1 = n2 + 1
                        n2 = n2 + min(60,len(sR)-i-60) - sR.count('-',i+60,i+120)

                        print('{: ^15}\t{}'.format('', sA[i:i+60]))

                        print('Query:{:>9}\t{}\t{}\n'.format(n3, sQ[i:i+60], n4))
                        n3 = n4 + 1
                        n4 = n4 + min(60,len(sQ)-i-60) - sQ.count('-',i+60,i+120)
            else:
                print("{}\t".format(sQId), end = '')
                if resPrint[0] == 0:
                    print("4\t*\t0\t255\t*\t*\t0\t0\t*\t*", end = '')
                else:
                    mapq = int(-4.343 * math.log(1-abs(resPrint[0]-resPrint[1])/float(resPrint[0])))
                    mapq = int(mapq + 4.99);
                    if mapq >= 254:
                        mapq = 254
                    if strand == 1:
                        print('16\t', end = '')
                    else:
                        print('0\t', end = '')
                    print('{}\t{}\t{}\t'.format(sRId, resPrint[2]+1, mapq), end = '')
                    print(sCigar, end = '')
                    print('\t*\t0\t0\t', end = '')
                    print(sQSeq[resPrint[4]:resPrint[5]+1] if strand==0 else sQRcSeq[resPrint[4]:resPrint[5]+1], end = '')
                    print('\t', end = '')
                    if sQQual:
                        if strand == 0:
                            print(sQQual[resPrint[4]:resPrint[5]+1], end = '')
                        else:
                            print(sQQual[-resPrint[4]-1:-resPrint[5]-1:-1])
                    else:
                        print('*', end = '')

                    print('\tAS:i:{}'.format(resPrint[0]), end = '')
                    print('\tNM:i:{}\t'.format(len(sA)-sA.count('|')), end = '')
                    if resPrint[1] > 0:
                        print('ZS:i:{}'.format(resPrint[1]), end = '')
                    else:
                        print('')


        ssw.init_destroy(qProfile)
        if args.bBest and not args.bProtien:
            ssw.init_destroy(qRcProfile)


# modifyed main function by Yuichi Shiraishi
def main2(query, target, min_score, nMatch = 2, nMismatch = 2, nOpen = 3, nExt = 1):

    lEle = []
    dRc = {} 
    dEle2Int = {}
    dInt2Ele = {}

    # init DNA score matrix
    lEle = ['A', 'C', 'G', 'T', 'N']
    for i,ele in enumerate(lEle):
        dEle2Int[ele] = i
        dEle2Int[ele.lower()] = i
        dInt2Ele[i] = ele
    nEleNum = len(lEle)
    lScore = [0 for i in range(nEleNum**2)]
    for i in range(nEleNum-1):
        for j in range(nEleNum-1):
            if lEle[i] == lEle[j]:
                lScore[i*nEleNum+j] = nMatch
            else:
                lScore[i*nEleNum+j] = - nMismatch

    # translate score matrix to ctypes
    mat = (len(lScore) * ct.c_int8) ()
    mat[:] = lScore

    # set flag
    nFlag = 0

    sLibPath = ""
    for ld_path in os.environ["LD_LIBRARY_PATH"].split(':'):
        # print ld_path
        if os.path.exists(ld_path + "/libssw.so"):
            sLibPath = ld_path # + "/libssw.so"
            break
    if sLibPath == "":
        print("cannot find libssw.so in LD_LIBRARY_PATH", file = sys.stderr)
        sys.exit(1)

    ssw = ssw_lib.CSsw(sLibPath)

    type2count = {"splice_junction_positive": 0, "splice_junction_negative": 0,
                  "intron_retention_positive": 0, "intron_retention_negative": 0}
    intron_retention_positive_supporting_reads = []

    # iterate query sequence
    for sQId,sQSeq,sQQual in read(query):

        # build query profile
        qNum = to_int(sQSeq, lEle, dEle2Int)
        qProfile = ssw.ssw_init(qNum, ct.c_int32(len(sQSeq)), mat, len(lEle), 2)

        # set mask len
        if len(sQSeq) > 30:
            nMaskLen = int(len(sQSeq) / 2)
        else:
            nMaskLen = 15


        # iter target sequence

        type2max_score = {"splice_junction_positive": 0, "splice_junction_negative": 0,
                          "intron_retention_positive": 0, "intron_retention_negative": 0}

        for sRId,sRSeq,_ in read(target):
            rNum = to_int(sRSeq, lEle, dEle2Int)

            # format ofres: (nScore, nScore2, nRefBeg, nRefEnd, nQryBeg, nQryEnd, nRefEnd2, nCigarLen, lCigar)
            res = align_one(ssw, qProfile, rNum, len(sRSeq), nOpen, nExt, nFlag, nMaskLen)

            # build cigar and trace back path
            strand = 0
            resPrint = res
            sCigar, sQ, sA, sR = buildPath(sQSeq, sRSeq, res[4], res[2], res[8])

            """
            print '\t'.join([sQId, sRId, sCigar, sQ, sA, sR])
            print sQ
            print sA
            print sR
            print res

            """

            temp_type = re.sub(r'_\d+$', '', sRId)
            if int(resPrint[0]) > type2max_score[temp_type]:
                type2max_score[temp_type] = int(resPrint[0])
     
            """    
            if int(resPrint[0]) > temp_max_score:
                temp_max_score = int(resPrint[0])
                temp_max_target = sRId
            """

        tnum = 0
        target_max_score = 0
        target_second_max_score = 0
        target_max_type = 0
        for ttype, tmax_score in sorted(type2max_score.items(), key = lambda x: x[1], reverse=True):
            if tnum == 0:
                target_max_score = tmax_score
                target_max_type = ttype
            elif tnum == 1:
                target_second_max_score = tmax_score
            else: continue
            tnum = tnum + 1
         
        if target_max_score <= min_score: continue
        if target_max_score == target_second_max_score: continue
 
        type2count[target_max_type] = type2count[target_max_type] + 1
        if target_max_type == "intron_retention_positive":
            intron_retention_positive_supporting_reads.append(sQId)

    return type2count, intron_retention_positive_supporting_reads

"""
if __name__ == '__main__':

    parser = ap.ArgumentParser()
    parser.add_argument('-l', '--sLibPath', default='', help='path of libssw.so')
    parser.add_argument('-m', '--nMatch', type=int, default=2, help='a positive integer as the score for a match in genome sequence alignment. [default: 2]')
    parser.add_argument('-x', '--nMismatch', type=int, default=2, help='a positive integer as the score for a mismatch in genome sequence alignment. [default: 2]')
    parser.add_argument('-o', '--nOpen', type=int, default=3, help='a positive integer as the penalty for the gap opening in genome sequence alignment. [default: 3]')
    parser.add_argument('-e', '--nExt', type=int, default=1, help='a positive integer as the penalty for the gap extension in genome sequence alignment. [default: 1]')
    parser.add_argument('-p', '--bProtien', action='store_true', help='Do protein sequence alignment. Without this option, the ssw_test will do genome sequence alignment. [default: False]')
    parser.add_argument('-a', '--sMatrix', default='', help='a file for either Blosum or Pam weight matrix. [default: Blosum50]')
    parser.add_argument('-c', '--bPath', action='store_true', help='Return the alignment path. [default: False]')
    parser.add_argument('-f', '--nThr', default=0, help='a positive integer. Only output the alignments with the Smith-Waterman score >= N.')
    parser.add_argument('-r', '--bBest', action='store_true', help='The best alignment will be picked between the original read alignment and the reverse complement read alignment. [default: False]')
    parser.add_argument('-s', '--bSam', action='store_true', help='Output in SAM format. [default: no header]')
    parser.add_argument('-header', '--bHeader', action='store_true', help='If -s is used, include header in SAM output.')
    parser.add_argument('target', help='targe file')
    parser.add_argument('query', help='query file')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()
    args = parser.parse_args()

    t1 = ti.default_timer()
    main(args)
    t2 = ti.default_timer()
    print >> sys.stderr, 'CPU time: {} seconds'.format(t2 - t1)

"""

if __name__ == '__main__':
    main2(sys.argv[1], sys.argv[2], int(sys.argv[3]))
    
