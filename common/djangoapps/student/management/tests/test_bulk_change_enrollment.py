"""Tests for the bulk_change_enrollment command."""
import ddt
from django.core.management import call_command
from django.core.management.base import CommandError
from mock import patch, call

from student.tests.factories import UserFactory, CourseModeFactory, CourseEnrollmentFactory
from student.models import CourseEnrollment, EVENT_NAME_ENROLLMENT_MODE_CHANGED
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


@ddt.ddt
class BulkChangeEnrollmentTests(SharedModuleStoreTestCase):
    """Tests for the bulk_change_enrollment command."""

    def setUp(self):
        super(BulkChangeEnrollmentTests, self).setUp()
        self.org = 'testX'
        self.course = CourseFactory.create(org=self.org)
        self.users = UserFactory.create_batch(5)
        CourseOverview.load_from_module_store(self.course.id)

    @patch('student.models.tracker')
    @ddt.data(('audit', 'honor'), ('honor', 'audit'))
    @ddt.unpack
    def test_bulk_convert(self, from_mode, to_mode, mock_tracker):
        """Verify that enrollments are changed correctly."""
        self._enroll_users(from_mode)
        CourseModeFactory(course_id=self.course.id, mode_slug=to_mode)

        # Verify that no users are in the `from` mode yet.
        self.assertEqual(len(CourseEnrollment.objects.filter(mode=to_mode, course_id=self.course.id)), 0)

        call_command(
            'bulk_change_enrollment',
            course=unicode(self.course.id),
            from_mode=from_mode,
            to_mode=to_mode,
            commit=True,
        )

        # Verify that all users have been moved -- if not, this will
        # raise CourseEnrollment.DoesNotExist
        for user in self.users:
            CourseEnrollment.objects.get(mode=to_mode, course_id=self.course.id, user=user)

            # Confirm the analytics event was emitted.
            mock_tracker.emit.assert_has_calls(  # pylint: disable=maybe-no-member
                [
                    call(
                        EVENT_NAME_ENROLLMENT_MODE_CHANGED,
                        {'course_id': unicode(self.course.id), 'user_id': user.id, 'mode': to_mode}
                    ),
                ]
            )

    @patch('student.models.tracker')
    @ddt.data(('audit', 'no-id-professional'), ('no-id-professional', 'audit'))
    @ddt.unpack
    def test_bulk_convert_with_org(self, from_mode, to_mode, mock_tracker):
        """Verify that enrollments are changed correctly when org was given."""
        self._enroll_users(from_mode)
        CourseModeFactory(course_id=self.course.id, mode_slug=to_mode)

        # Verify that no users are in the `from` mode yet.
        self.assertEqual(len(CourseEnrollment.objects.filter(mode=to_mode, course_id=self.course.id)), 0)

        call_command(
            'bulk_change_enrollment',
            org=self.org,
            from_mode=from_mode,
            to_mode=to_mode,
            commit=True,
        )

        # Verify that all users have been moved -- if not, this will
        # raise CourseEnrollment.DoesNotExist
        for user in self.users:
            CourseEnrollment.objects.get(mode=to_mode, course_id=self.course.id, user=user)

            # Confirm the analytics event was emitted.
            mock_tracker.emit.assert_has_calls(  # pylint: disable=maybe-no-member
                [
                    call(
                        EVENT_NAME_ENROLLMENT_MODE_CHANGED,
                        {'course_id': unicode(self.course.id), 'user_id': user.id, 'mode': to_mode}
                    ),
                ]
            )

    def test_with_org_and_course_key(self):
        """Verify that command raises CommandError when `org` and `course_key` both are given."""
        self._enroll_users('audit')
        CourseModeFactory(course_id=self.course.id, mode_slug='no-id-professional')

        with self.assertRaises(CommandError):
            call_command(
                'bulk_change_enrollment',
                org=self.org,
                course=unicode(self.course.id),
                from_mode='audit',
                to_mode='no-id-professional',
                commit=True,
            )

    def test_with_invalid_org(self):
        """Verify that command raises CommandError when invalid `org` is given."""
        self._enroll_users('audit')
        CourseModeFactory(course_id=self.course.id, mode_slug='no-id-professional')

        with self.assertRaises(CommandError):
            call_command(
                'bulk_change_enrollment',
                org='fakeX',
                from_mode='audit',
                to_mode='no-id-professional',
                commit=True,
            )

    def test_without_commit(self):
        """Verify that nothing happens when the `commit` flag is not given."""
        self._enroll_users('audit')
        CourseModeFactory(course_id=self.course.id, mode_slug='honor')

        call_command(
            'bulk_change_enrollment',
            course=unicode(self.course.id),
            from_mode='audit',
            to_mode='honor',
        )

        # Verify that no users are in the honor mode.
        self.assertEqual(len(CourseEnrollment.objects.filter(mode='honor', course_id=self.course.id)), 0)

    def test_without_to_mode(self):
        """Verify that the command fails when the `to_mode` argument does not exist."""
        self._enroll_users('audit')
        CourseModeFactory(course_id=self.course.id, mode_slug='audit')

        with self.assertRaises(CommandError):
            call_command(
                'bulk_change_enrollment',
                course=unicode(self.course.id),
                from_mode='audit',
                to_mode='honor',
            )

    @ddt.data('from_mode', 'to_mode', 'course')
    def test_without_options(self, option):
        """Verify that the command fails when some options are not given."""
        command_options = {
            'from_mode': 'audit',
            'to_mode': 'honor',
            'course': unicode(self.course.id),
        }
        command_options.pop(option)

        with self.assertRaises(CommandError):
            call_command('bulk_change_enrollment', **command_options)

    def test_bad_course_id(self):
        """Verify that the command fails when the given course ID does not parse."""
        with self.assertRaises(CommandError):
            call_command('bulk_change_enrollment', from_mode='audit', to_mode='honor', course='yolo', commit=True)

    def test_nonexistent_course_id(self):
        """Verify that the command fails when the given course does not exist."""
        with self.assertRaises(CommandError):
            call_command(
                'bulk_change_enrollment',
                from_mode='audit',
                to_mode='honor',
                course='course-v1:testX+test+2016',
                commit=True
            )

    def _enroll_users(self, mode):
        """Enroll users in the given mode."""
        for user in self.users:
            CourseEnrollmentFactory(mode=mode, course_id=self.course.id, user=user)
