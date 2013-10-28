# -*- coding: utf-8 -*-
"""
Functional tests using Selenium.

See: ``docs/testing/selenium.rst`` for details.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils.unittest.case import skipUnless, skipIf


from bluebottle.geo import models as geo_models
from onepercentclub.tests.utils import OnePercentSeleniumTestCase


from ..models import Project, ProjectPhases, ProjectPitch, ProjectTheme
from .unittests import ProjectTestsMixin


import os
import time


@skipUnless(getattr(settings, 'SELENIUM_TESTS', False),
        'Selenium tests disabled. Set SELENIUM_TESTS = True in your settings.py to enable.')
class ProjectSeleniumTests(ProjectTestsMixin, OnePercentSeleniumTestCase):
    """
    Selenium tests for Projects.
    """
    def setUp(self):
        self.projects = dict([(slugify(title), title) for title in [
            u'Women first 2', u'Mobile payments for everyone 2!', u'Schools for children 2'
        ]])

        User = get_user_model()
        # Create and activate user.
        self.user = User.objects.create_user('johndoe@example.com', 'secret')

        for slug, title in self.projects.items():
            project = self.create_project(title=title, slug=slug, money_asked=100000, owner=self.user)
            project.projectcampaign.money_donated = 0
            project.projectcampaign.save()

    def visit_project_list_page(self, lang_code=None):
        self.visit_path('/projects', lang_code)

        self.assertTrue(self.browser.is_element_present_by_css('.item.item-project'),
                'Cannot load the project list page.')

    def test_navigate_to_project_list_page(self):
        """
        Test navigate to the project list page.
        """
        self.visit_homepage()

        # Find the link to the Projects page and click it.
        self.browser.find_link_by_text('1%Projects').first.click()

        # Validate that we are on the intended page.
        self.assertTrue(self.browser.is_element_present_by_css('.item.item-project'),
                'Cannot load the project list page.')

        self.assertEqual(self.browser.url, '%s/en/#!/projects' % self.live_server_url)
        self.assertEqual(self.browser.title, '1%Club - Share a little. Change the world')

    def test_view_project_list_page(self):
        """
        Test view the project list page correctly.
        """
        self.visit_project_list_page()

        # Besides the waiting for JS to kick in, we also need to wait for the funds raised animation to finish.
        time.sleep(2)

        def convert_money_to_int(money_text):
            return int(money_text.strip(u'€ ').replace('.', '').replace(',', ''))

        # NOTE: Due to a recent change, its harder to calculate/get the financiel data from the front end.
        # Hence, these calculations are commented. Perhaps enable in the future if this data becomes available again.

        # Create a dict of all projects on the web page.
        web_projects = []
        for p in self.browser.find_by_css('.item.item-project'):
            # NOTE: donated class name should be read as "to go"...
            donated = convert_money_to_int(p.find_by_css('.donated').first.text)
            #asked = convert_money_to_int(p.find_by_css('.asked').first.text)

            web_projects.append({
                'title': p.find_by_css('h3').first.text,
                'money_needed': donated,
                #'money_asked': asked,
            })

            # Validate the donation slider.
            # NOTE: It's an animation. We expect it to be done after a few seconds.
            #expected_slider_value = ((Decimal('100') / asked) * donated)
            #web_slider_value = Decimal(css_dict(p.find_by_css('.donate-progress').first['style'])['width'].strip('%'))

            # We allow a small delta to deviate.
            #self.assertAlmostEqual(web_slider_value, expected_slider_value, delta=1)

        # Make sure there are some projects to compare.
        self.assertTrue(len(web_projects) > 0)

        # Create dict of projects in the database.
        expected_projects = []
        for p in Project.objects.filter(phase=ProjectPhases.campaign).order_by('popularity')[:len(web_projects)]:
            expected_projects.append({
                'title': p.title.upper(),  # Uppercase the title for comparison.
                'money_needed': int(round(p.projectcampaign.money_needed / 100.0)),
                #'money_asked': int(round(p.projectcampaign.money_asked / 100.0))
            })

        # Compare all projects found on the web page with those in the database, in the same order.
        self.assertListEqual(web_projects, expected_projects)

    def test_upload_pitch_picture(self):
        """ Test that pitch picture uploads work. """
        
        # create project (with pitch)
        slug = 'picture-upload'
        project = self.create_project(title='Test picture upload', owner=self.user, phase='pitch', slug=slug)
        pitch = project.projectpitch # raises error if no pitch is present
        # create theme
        pitch.theme = ProjectTheme.objects.create(name='Tests', name_nl='Testen', slug='tests')
        # create country etc.
        region = geo_models.Region.objects.create(name='Foo', numeric_code=123)
        subregion = geo_models.SubRegion.objects.create(name='Bar', numeric_code=456, region=region)
        pitch.country = geo_models.Country.objects.create(
                            name='baz', 
                            subregion=subregion,
                            numeric_code=789,
                            alpha2_code='AF',
                            oda_recipient=True)

        pitch.latitude = '52.3731'
        pitch.longitude = '4.8922'
        pitch.save()



        self.login(self.user.email, 'secret')
        # navigation itself has been tested before...
        self.visit_path('/my/projects/')

        self.browser.find_link_by_itext('continue pitch').first.click()

        self.browser.find_link_by_itext('Media').first.click()
        
        # get preview div
        self.assertTrue(self.browser.find_by_css('div.preview').has_class('empty'))
        
        file_path = os.path.join(settings.PROJECT_ROOT, 'static', 'tests', 'kitten_snow.jpg')
        self.browser.attach_file('image', file_path)

        # test if preview is there
        preview = self.browser.find_by_css('div.preview')
        self.assertFalse(preview.has_class('empty'))
        img = preview.find_by_tag('img').first
        self.assertNotEqual(img['src'], '%simages/empty.png' % settings.STATIC_URL)

        # save
        self.browser.find_by_tag('form').first.find_by_tag('button').first.click()

        # return to media form
        time.sleep(2) # link has to update
        self.browser.find_link_by_itext('media').first.click()
        
        # check that the src of the image is correctly set (no base64 stuff)
        src = self.browser.find_by_css('div.preview').first.find_by_tag('img').first['src']
        self.assertEqual('.jpg', src[-4:])

    def test_upload_multiple_wallpost_images(self):
        """ Test uploading multiple images in a media wallpost """

        self.login(self.user.email, 'secret')
        self.visit_project_list_page()

        # pick a project
        self.browser.find_by_css('.item.item-project').first.find_by_tag('a').first.click()

        form = self.browser.find_by_css('form.ember-view')
        form_data = {
            'input[placeholder="Keep it short and simple"]': 'My wallpost',
            'textarea[name="wallpost-update"]': 'These are some sample pictures from this non-existent project!',
        }
        self.browser.fill_form_by_css(form, form_data)

        # verify that no previews are there yet
        ul = form.find_by_css('ul.wallpost-photos').first
        previews = ul.find_by_tag('li')
        self.assertEqual(0, len(previews))


        # attach file
        file_path = os.path.join(settings.PROJECT_ROOT, 'static', 'tests', 'kitten_snow.jpg')
        self.browser.attach_file('wallpost-photo', file_path)

        # wait a bit, processing...
        time.sleep(3)

        # verify that one picture was added
        form = self.browser.find_by_css('form.ember-view')
        ul = form.find_by_css('ul.wallpost-photos').first
        previews = ul.find_by_tag('li')

        self.assertEqual(1, len(previews))

        # verify that a second picture was added
        file_path = os.path.join(settings.PROJECT_ROOT, 'static', 'tests', 'chameleon.jpg')
        self.browser.attach_file('wallpost-photo', file_path)
        
        # wait a bit, processing...
        time.sleep(3)

        form = self.browser.find_by_css('form.ember-view')
        ul = form.find_by_css('ul.wallpost-photos').first
        previews = ul.find_by_tag('li')
        self.assertEqual(2, len(previews))
