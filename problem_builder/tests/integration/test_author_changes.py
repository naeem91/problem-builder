"""
If an author makes changes to the block after students have started using it, will bad things
happen?
"""
import time
from .base_test import ProblemBuilderBaseTest, MentoringAssessmentBaseTest
import re


class AuthorChangesTest(ProblemBuilderBaseTest):
    """
    Test various scenarios involving author changes made to a block already in use by students
    """
    def setUp(self):
        super(AuthorChangesTest, self).setUp()
        self.load_scenario("author_changes.xml", {"mode": "standard"}, load_immediately=False)
        self.refresh_page()

    def refresh_page(self):
        """
        [Re]load the page with our scenario
        """
        self.pb_block_dom = self.go_to_view("student_view")
        # At this point the ajax request that initializes the Mentoring block
        # might be still in progres. Race conditions resulting in duplicate field data
        # can occur if we try to reload the block at the same time.
        # Sleep 200ms to wait for the ajax request to finish, unfortunately I wasn't
        # able to find a better way.
        time.sleep(0.2)
        self.reload_pb_block()

    def reload_pb_block(self):
        """
        [Re]load the Problem Builder block, potentially with updated field data
        """
        vertical = self.load_root_xblock()
        self.pb_block = vertical.runtime.get_block(vertical.children[0])

    def submit_answers(self, q1_answer='yes', q2_answer='elegance', q3_answer="It's boring."):
        """ Answer all three questions in the 'author_changes.xml' scenario correctly """
        self.pb_block_dom.find_element_by_css_selector('input[name=q1][value={}]'.format(q1_answer)).click()
        self.pb_block_dom.find_element_by_css_selector('input[name=q2][value={}]'.format(q2_answer)).click()
        self.pb_block_dom.find_element_by_css_selector('textarea').send_keys(q3_answer)
        self.click_submit(self.pb_block_dom)

    def test_delete_question(self):
        """ Test what the block behaves correctly when deleting a question """
        # First, submit an answer to each of the three questions, but get the second question wrong:
        self.submit_answers(q2_answer='bugs')
        self.reload_pb_block()
        self.assertEqual(self.pb_block.score.percentage, 67)

        # Delete the second question:
        self.pb_block.children = [self.pb_block.children[0], self.pb_block.children[2]]
        self.pb_block.save()
        self.reload_pb_block()

        # Now that the wrong question is deleted, the student should have a perfect score:
        self.assertEqual(self.pb_block.score.percentage, 100)
        # NOTE: This is questionable, since the block does not send a new 'grade' event to the
        # LMS. So the LMS 'grade' (based on the event sent when the student actually submitted
        # the answers) and the block's current 'score' may be different.

    def test_reweight_question(self):
        """ Test what the block behaves correctly when changing the weight of a question """
        # First, submit an answer to each of the three questions, but get the first question wrong:
        self.submit_answers(q1_answer='no')
        self.reload_pb_block()
        self.assertEqual(self.pb_block.score.percentage, 67)

        # Re-weight Q1 to '5':
        q1 = self.pb_block.runtime.get_block(self.pb_block.children[0])
        q1.weight = 5
        q1.save()
        self.reload_pb_block()
        self.assertEqual(self.pb_block.score.percentage, 29)  # 29% is 2 out of 7 (5+1+1)

        # Delete Q2 (the MRQ)
        self.pb_block.children = [self.pb_block.children[0], self.pb_block.children[2]]
        self.pb_block.save()
        self.reload_pb_block()

        # Now, the student's score should be 1 out of 6 (only q3 is correct):
        self.assertEqual(self.pb_block.score.percentage, 17)


class AuthorChangesAssessmentTest(MentoringAssessmentBaseTest):
    """
    Test various scenarios involving author changes made to an assessment block already in use
    """
    def test_delete_question(self):
        """ Test that the assessment behaves correctly when deleting a question. """
        pb_block_dom, controls = self.load_assessment_scenario("author_changes.xml", {"mode": "assessment"})

        # Answer each question, getting the first question wrong:
        mentoring = pb_block_dom.find_element_by_css_selector(".mentoring")
        self.answer_mcq(number=1, name="q1", value="no", mentoring=mentoring, controls=controls, is_last=False)
        self.answer_mcq(number=2, name="q2", value="elegance", mentoring=mentoring, controls=controls, is_last=False)

        pb_block_dom.find_element_by_css_selector('textarea').send_keys("Hello world")
        controls.submit.click()
        self.wait_until_clickable(controls.review)
        controls.review.click()
        self.wait_until_hidden(controls.review)

        # Delete question 3:
        vertical = self.load_root_xblock()
        pb_block = vertical.runtime.get_block(vertical.children[0])
        self.assertEqual(pb_block.score.percentage, 67)
        pb_block.children = [pb_block.children[0], pb_block.children[1]]
        pb_block.save()
        pb_block_dom, controls = self.go_to_assessment()

        self.assertIn("You scored 50% on this assessment.", pb_block_dom.text)
        self.assertIn("You answered 1 question correctly.", pb_block_dom.text)
        self.assertIn("You answered 1 question incorrectly.", pb_block_dom.text)

        controls.try_again.click()
        self.wait_until_hidden(controls.try_again)

        # Now answer again, getting a perfect score:
        mentoring = pb_block_dom.find_element_by_css_selector(".mentoring")
        self.answer_mcq(number=1, name="q1", value="yes", mentoring=mentoring, controls=controls, is_last=False)
        self.answer_mcq(number=2, name="q2", value="elegance", mentoring=mentoring, controls=controls, is_last=True)
        self.assertIn("You scored 100% on this assessment.", mentoring.text)
