#!/usr/bin/env python

"""
Parser a collection of orphanet files together to get a useable lookup table of 
diseases with associated genotypic and phenotypic OMIMs as well as inheritance
patterns.
"""


import os
import sys
import logging

from collections import defaultdict
import xml.etree.ElementTree as ET


__author__ = 'Tal Friedman (talf301@gmail.com)'

class Disease:
    def __init__(self):
        self.pheno = []
        self.inheritance = []
        self.geno = []

class Orphanet:
    def __init__(self, lookup_filename, inher_filename, geno_pheno_filename):
        self.lookup = self.parse_lookup(lookup_filename)
        self.inheritance = self.parse_inheritance(inher_filename, self.lookup)
        #counter for when we write stats
        self.counter = self.parse_geno_pheno(geno_pheno_filename,self.lookup)
    
    @classmethod
    def parse_lookup(cls, filename):
        tree = ET.parse(filename)
        root = tree.getroot()
        lookup = defaultdict(Disease) # orphanet -> omim
        for disorder in root.findall('.//Disorder'):
            orphanum = disorder.find('OrphaNumber').text
            for ref in disorder.findall('./ExternalReferenceList/ExternalReference'):
                if ref.find('Source').text == 'OMIM':
                    omim = ref.find('Reference').text
                    # Ensure Orphanum and OMIM are numeric
                    try:
                        int(omim)
                        int(orphanum)
                    except ValueError:
                        logging.error("Malformed OMIM or Orphanum at %s" % orphanum)
                    lookup[orphanum].pheno.append(omim)
        return lookup

    @classmethod
    def parse_inheritance(cls, filename, lookup):
        tree = ET.parse(filename)
        root = tree.getroot()
        inheritance = defaultdict(list) # omim -> inheritance pattern list
        for disorder in root.findall('.//Disorder'):
            orphanum = disorder.find('OrphaNumber').text
            #ensure that this disorder has an omim number
            try:
                ids = lookup[orphanum].pheno
            except KeyError:
                continue
            for inher in  disorder.findall('./TypeOfInheritanceList/TypeOfInheritance'):
                pattern = inher.find('Name').text
                assert pattern in ['X-linked dominant', 'Mitochondrial inheritance', \
                        'Unknown', 'Autosomal recessive', 'Multigenic/multifactorial', \
                        'X-linked recessive', 'Sporadic', 'Autosomal dominant', \
                        'No data available'], "Unrecognized inheritance pattern %s" % pattern
                lookup[orphanum].inheritance.append(pattern)
                for id in ids:
                    inheritance[id].append(pattern)
        return inheritance    
        
    @classmethod
    def parse_geno_pheno(cls, filename, lookup):
        tree = ET.parse(filename)
        root = tree.getroot()
        counter = 0
        for disorder in root.findall('.//Disorder'):
            restart = False
            orphanum = disorder.find('OrphaNumber').text
            for ref in disorder.findall('.//ExternalReferenceList/ExternalReference'):
                if ref.find('Source').text == 'OMIM':
                    omim = ref.find('Reference').text
                    # Ensure OMIM is numeric
                    try:
                        int(omim)
                    except ValueError:
                        logging.error("Malformed OMIM %s" % omim)

                    try:
                        lookup[orphanum].geno.append(omim)           
                    except KeyError:
                        restart = True
                        counter += 1
                        break
            if restart:
                continue
        logging.warning("%d Disorders were unmatched to a phenotypic omim" % counter)
        return counter

    def write_file(self, filename):
        with open(filename, 'w') as out:
            for k in self.lookup.keys():
                out.write(str(self.lookup[k]) + '\n')

    def write_stats(self, filename):
        with open(filename, 'w') as out:
            n_ideal = 0
            n_miss_inher = 0
            n_miss_pheno = self.counter
            n_miss_geno = 0
            n_one_pheno = 0
            n_one_geno = 0
            n_many_geno = 0
            n_many_pheno = 0
            for o in self.lookup.itervalues():
                if len(o.pheno) == 1 and len(o.inheritance) == 1 and len(o.geno) == 1: n_ideal += 1
                if len(o.inheritance) == 0: n_miss_inher += 1
                if len(o.geno) == 0: n_miss_geno += 1
                if len(o.pheno) == 1: n_one_pheno += 1
                if len(o.geno) == 1: n_one_geno += 1
                if len(o.pheno) > 1: n_many_pheno += 1
                if len(o.geno) > 1: n_many_geno += 1
            
            out.write("PHENO OMIM:" + '\n')
            out.write(str(n_miss_pheno) + " entries missing OMIM Pheno entry\n")
            out.write(str(n_one_pheno) + " entries with one OMIM Pheno entry\n")
            out.write(str(n_many_pheno) + " entries with many OMIM pheno entries\n")
            out.write("INERITANCE:" + '\n')
            out.write(str(n_miss_inher) + " entries missing inheritance pattern\n")
            out.write("GENO OMIM:" + '\n')
            out.write(str(n_miss_geno) + " entries missing OMIM Geno entry\n")
            out.write(str(n_one_geno) + " entries with one OMIM Geno entry\n")
            out.write(str(n_many_geno) + " entries with many OMIM Geno entries\n")
            out.write(str(n_ideal) + " ideal entries (1 of each)")
    
    @classmethod
    def has_pattern(cls, patterns, o):
        return any(x in patterns for x in o.inheritance)

    @classmethod
    def has_pheno(cls, omim_dict, o):
        return o.pheno[0] in omim_dict

    @classmethod
    #ensure that all elements of lookup are entirely useable
    def correct_lookup(cls, lookup, omim_dict, rev_hgmd, Inheritance=None):
        #get ideal orphanet cases
        newlook = {k:v for k,v in lookup.iteritems() if len(v.pheno) == 1 and len(v.inheritance) == 1 and len(v.geno) == 1}
        #get the right disease set based on inheritance
        if Inheritance:
            patterns = []
            if 'AD' in Inheritance:
                 patterns.append('Autosomal dominant')
            if 'AR' in Inheritance:
                patterns.append('Autosomal recessive')
            newlook ={k:v for k,v in newlook.iteritems() if cls.has_pattern(patterns, v)}
        
        #ensure all orphanet cases have phenotypic annotations
        lookup = {k:v for k,v in newlook.iteritems() if cls.has_pheno(omim_dict, v)}
        #ensure all orphanet cases have at least one associated variant
        newlook = {}
        for k, o in lookup.iteritems():
            try:
                a = rev_hgmd[o.geno[0]]
                newlook[k] = o
            except KeyError:
                pass
        return newlook

if __name__ == '__main__':
    orph = Orphanet('/dupa-filer/talf/matchingsim/patients/orphanet_lookup.xml', '/dupa-filer/talf/matchingsim/patients/orphanet_inher.xml', '/dupa-filer/talf/matchingsim/patients/orphanet_geno_pheno.xml')
    orph.write_file('orphanet_parsed.txt')
    orph.write_stats('orphanet_parsed.log')
