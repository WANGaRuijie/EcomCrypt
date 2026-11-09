import sys
import unittest
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evidence_review import evidence_review, prefer_abstract, persist_reviews, retain_editorial_followup
from directory import read_json,write_json
from author_discovery import rank_authors
from metadata import _openalex_record
from expand import abstract_text


class RecallTests(unittest.TestCase):
    def test_editorial_hold_survives_a_resolved_abstract_only_label(self):
        followup={'status':'review_evidence','reason':'Inspect the collusion argument in the original paper.'}
        previous={'editorial_review_required':True,'followup':followup}
        self.assertEqual(retain_editorial_followup(previous,None),followup)

    def test_explicit_editorial_resolution_releases_hold(self):
        previous={'editorial_review_required':True,'editorial_resolution':{'decision':'exclude_scope'}}
        self.assertIsNone(retain_editorial_followup(previous,None))

    def test_ordinary_abstract_review_is_not_changed_into_editorial_hold(self):
        self.assertIsNone(retain_editorial_followup({},None))

    def test_classics_with_missing_or_short_abstracts_remain_reviewable(self):
        for title in ['Bitcoin mining pools: A cooperative game theoretic analysis',
                      "Bitcoin's underlying incentives", 'Transaction fee mechanisms robust to welfare-increasing collusion',
                      'What can cryptography do for decentralized mechanism design?']:
            for decision in ['out','adjacent','uncertain']:
                with self.subTest(title=title,decision=decision):
                    result=evidence_review({'title':title},{'decision':decision},'The economic forces behind Bitcoin.')
                    self.assertEqual(result['status'],'review_evidence')

    def test_invalid_excerpt_cannot_disappear_even_without_title_keywords(self):
        self.assertIsNotNone(evidence_review({'title':'Red balloons'},
             {'decision':'uncertain','evidence_validation':'invalid_excerpt_requires_review'},'full abstract'))

    def test_irrelevant_title_with_resolved_negative_evidence_is_not_rescued(self):
        self.assertIsNone(evidence_review({'title':'Combinatorial assortment optimization'}, {'decision':'out'},'Retail optimization'))

    def test_negative_label_without_any_recovered_evidence_is_not_terminal(self):
        self.assertEqual(evidence_review({'title':'Uninformative title'}, {'decision':'out'},'')['status'],'review_evidence')

    def test_empty_enrichment_cannot_destroy_abstract(self):
        self.assertEqual(prefer_abstract('Existing evidence',''),'Existing evidence')

    def test_review_queue_keeps_resolution_and_original_classification_on_repeat(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path=Path(folder)/'queue.json'
            row={'status':'review_evidence','classification':{'id':'W1','decision':'uncertain'},
                 'evidence_input':{'abstract':'','raw_input':{'title':'Bitcoin incentives'}},
                 'followup':{'status':'review_evidence'}}
            persist_reviews(path,[row],'screen.json')
            document=read_json(path);document['records'][0]['editorial_resolution']={'decision':'exclude','reason':'Primary text reviewed'}
            write_json(path,document)
            persist_reviews(path,[row],'screen.json')
            saved=read_json(path)['records'][0]
            self.assertEqual(saved['status'],'resolved')
            self.assertEqual(len(saved['classification_history']),1)

    def test_authors_of_nonpriority_adopted_papers_are_eligible_and_exact_ids_dedup(self):
        directory={'papers':[{'id':'discovered-test','researcher_ids':['r1','r2'],'venue':'Unknown'}],
            'researchers':[{'id':r,'name':'A Researcher','identity_ids':{'openalex':'A1'}} for r in ['r1','r2']]}
        ranked,_=rank_authors(directory)
        self.assertEqual(len(ranked),1)
        self.assertEqual(ranked[0]['evidence'],['discovered-test'])

    def test_author_linked_only_to_journal_edition_is_not_omitted(self):
        directory={'papers':[{'id':'gs-015','researcher_ids':[],
            'publications':[{'researcher_ids':['r1']}]}],
            'researchers':[{'id':'r1','name':'Nick Arnosti','identity_ids':{'openalex':'A1'}}]}
        ranked,_=rank_authors(directory)
        self.assertEqual(ranked[0]['id'],'A1')

    def test_harvest_preserves_optional_abstract_evidence(self):
        row=_openalex_record({'id':'https://openalex.org/W1','abstract_inverted_index':{'Bitcoin':[0],'incentives':[1]}})
        self.assertEqual(row['abstract'],'Bitcoin incentives')

    def test_abstract_tail_is_not_silently_cut_before_strategic_evidence(self):
        index={'background':list(range(300)),'incentive-compatible':[300]}
        self.assertTrue(abstract_text(index).endswith('incentive-compatible'))
