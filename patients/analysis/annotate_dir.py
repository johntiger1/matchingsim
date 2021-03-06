#!/usr/bin/env python

#Given a directory, will add a corresponding text file for each patient containing info on Genotypic OMIM, Phenotypic OMIM, Variant, and rank as given by exomizer 

__author__ = 'Tal Friedman'

import os
import sys
import logging

from hgmd import HGMD
from omim import MIM
from orpha import Orphanet
from argparse import ArgumentParser

def get_last_line(path):
    with open(path) as file:
        for line in file:
            s = line
    return [s]

def get_last_recessive(path):
    with open(path) as file:
        cont = list(file)
        info = cont[-1].split('\t')
        if info[-1].strip() == '1/1' or info[-1].strip() == '1|1':
            return cont[-1:]
        else:
            return cont[-2:]

def get_actual_lines(path):
    with open(path) as file:    
        return filter(lambda x: not x.startswith('#'), list(file))

def get_rank(v, elines):
    for i, e in enumerate(elines):
        if is_match(v, e):
            return i + 1
    return "Not found"

def is_match(linevs, linee):
    for linev in linevs:
        infov = linev.split('\t')
        infoe = linee.split('\t')
        if infov[0] == infoe[0][3:] and infov[1] == infoe[1]:
            return True
    return False

def get_by_variant(v, hgmd, lookup):
    id = next(x for x in hgmd.entries if x.chrom == v[0].split('\t')[0] and x.loc == v[0].split('\t')[1]).omimid    
    pheno_id = next(x for x in lookup.itervalues() if x.geno[0] == id).pheno[0]
    return id, pheno_id

def get_by_name(vcf, lookup):
    orphanum = vcf.split('_')[-2]
    id = lookup[orphanum].geno[0]
    pheno_id = lookup[orphanum].pheno[0]
    return orphanum, id, pheno_id

def script(path, R):
    hgmd = HGMD('/dupa-filer/talf/matchingsim/patients/hgmd_correct.jv.vcf')
    rev_hgmd = hgmd.get_by_omim()
    orph = Orphanet('/dupa-filer/talf/matchingsim/patients/orphanet_lookup.xml', '/dupa-filer/talf/matchingsim/patients/orphanet_inher.xml', '/dupa-filer/talf/matchingsim/patients/orphanet_geno_pheno.xml')
    omim = MIM('/dupa-filer/talf/matchingsim/patients/phenotype_annotation.tab')
    omim = filter(lambda x:x.db == 'OMIM', omim.diseases)
    omim_dict = {dis.id:dis for dis in omim}
    lookup = orph.filter_lookup(orph.lookup,omim_dict,rev_hgmd)
    contents = os.listdir(path)
    vcf_files = filter(lambda f: f.endswith('.vcf'), contents)
    ezr_files = filter(lambda f: f.endswith('.ezr'), contents)
    if len(vcf_files) > len(ezr_files):
        vcf_files = filter(lambda f: ''.join([f[:-4], '.ezr']) in ezr_files, vcf_files)
    vcf_files.sort()
    ezr_files.sort()

    for vcf, ezr in zip(vcf_files, ezr_files):
        if R:
            v = get_last_recessive(os.path.join(path, vcf))
        else:
            v = get_last_line(os.path.join(path,vcf))

        elines = get_actual_lines(os.path.join(path, ezr))
        rank = get_rank(v, elines)
        try:
            orph, id, pheno_id = get_by_name(vcf, lookup) 
        except IndexError, KeyError:
            #try:
            #    id, pheno_id = get_by_variant(v, hgmd, lookup)
            #except StopIteration:
            #    logging.error("Couldn't find associated variant %s" % v[0])
            #    logging.error("File %s" % vcf)
            #    continue
            logging.error("Name not found or incorrectly formatted %s" % vcf)
        
        with open(os.path.join(path, vcf[:-4] + '.txt'), 'w') as file:
            file.write('Rank of inserted variant: ' + str(rank) + '\n')
            file.write('Variant: ' + str(v[0]).strip() + '\n')
            if len(v) > 1:
                file.write('Variant: ' + str(v[1]).strip() + '\n')
            file.write('Genotypic OMIM: ' + str(id) + '\n')
            file.write('Phenotypic OMIM: ' + str(pheno_id) + '\n')
            if orph:
                file.write('Orphanum: ' + str(orph) + '\n')
            
def parse_args(args):
    parser = ArgumentParser(description='Add a text file annotation for each vcf/ezr pair in a directory')
    parser.add_argument('path',metavar='DIR',help='the directory where vcf/ezr files are located')
    parser.add_argument('-R',help='files to analyze were infected with autosomal recessive diseases (default is AD)', action='store_true')
    return parser.parse_args(args)

def main(args = sys.argv[1:]):
    args = parse_args(args)
    script(**vars(args))

if __name__ == '__main__':
    sys.exit(main())
