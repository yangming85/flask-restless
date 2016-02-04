# test_deleting.py - unit tests for deleting resources
#
# Copyright 2011 Lincoln de Sousa <lincoln@comum.org>.
# Copyright 2012, 2013, 2014, 2015, 2016 Jeffrey Finkelstein
#           <jeffrey.finkelstein@gmail.com> and contributors.
#
# This file is part of Flask-Restless.
#
# Flask-Restless is distributed under both the GNU Affero General Public
# License version 3 and under the 3-clause BSD license. For more
# information, see LICENSE.AGPL and LICENSE.BSD.
"""Unit tests for deleting resources from endpoints generated by
Flask-Restless.

This module includes tests for additional functionality that is not
already tested by :mod:`test_jsonapi`, the package that guarantees
Flask-Restless meets the minimum requirements of the JSON API
specification.

"""
try:
    from flask.ext.sqlalchemy import SQLAlchemy
except ImportError:
    has_flask_sqlalchemy = False
else:
    has_flask_sqlalchemy = True
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy.orm import relationship

from flask.ext.restless import APIManager
from flask.ext.restless import CONTENT_TYPE
from flask.ext.restless import ProcessingException

from .helpers import dumps
from .helpers import loads
from .helpers import FlaskTestBase
from .helpers import ManagerTestBase
from .helpers import MSIE8_UA
from .helpers import MSIE9_UA
from .helpers import skip_unless
from .helpers import unregister_fsa_session_signals


class TestDeleting(ManagerTestBase):
    """Tests for deleting resources."""

    def setup(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person`
        and :class:`TestSupport.Article` models.

        """
        super(TestDeleting, self).setup()

        class Article(self.Base):
            __tablename__ = 'article'
            id = Column(Integer, primary_key=True)
            author = relationship('Person')
            author_id = Column(Integer, ForeignKey('person.id'))

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)

        self.Article = Article
        self.Person = Person
        self.Base.metadata.create_all()
        self.manager.create_api(Article, methods=['DELETE'])
        self.manager.create_api(Person, methods=['DELETE'])

    def test_related_resource_url_forbidden(self):
        """Tests that :http:method:`delete` requests to a related resource URL
        are forbidden.

        """
        article = self.Article(id=1)
        person = self.Person(id=1)
        article.author = person
        self.session.add_all([article, person])
        self.session.commit()
        data = dict(data=dict(type='person', id=1))
        response = self.app.delete('/api/article/1/author', data=dumps(data))
        assert response.status_code == 405
        # TODO check error message here
        assert article.author is person

    def test_correct_content_type(self):
        """Tests that the server responds with :http:status:`201` if the
        request has the correct JSON API content type.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.delete('/api/person/1', content_type=CONTENT_TYPE)
        assert response.status_code == 204
        assert response.headers['Content-Type'] == CONTENT_TYPE

    def test_no_content_type(self):
        """Tests that the server responds with :http:status:`415` if the
        request has no content type.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.delete('/api/person/1', content_type=None)
        assert response.status_code == 415
        assert response.headers['Content-Type'] == CONTENT_TYPE

    def test_wrong_content_type(self):
        """Tests that the server responds with :http:status:`415` if the
        request has the wrong content type.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        bad_content_types = ('application/json', 'application/javascript')
        for content_type in bad_content_types:
            response = self.app.delete('/api/person/1',
                                       content_type=content_type)
            assert response.status_code == 415
            assert response.headers['Content-Type'] == CONTENT_TYPE

    def test_msie8(self):
        """Tests for compatibility with Microsoft Internet Explorer 8.

        According to issue #267, making requests using JavaScript from MSIE8
        does not allow changing the content type of the request (it is always
        ``text/html``). Therefore Flask-Restless should ignore the content type
        when a request is coming from this client.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        headers = {'User-Agent': MSIE8_UA}
        content_type = 'text/html'
        response = self.app.delete('/api/person/1', headers=headers,
                                   content_type=content_type)
        assert response.status_code == 204

    def test_msie9(self):
        """Tests for compatibility with Microsoft Internet Explorer 9.

        According to issue #267, making requests using JavaScript from MSIE9
        does not allow changing the content type of the request (it is always
        ``text/html``). Therefore Flask-Restless should ignore the content type
        when a request is coming from this client.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        headers = {'User-Agent': MSIE9_UA}
        content_type = 'text/html'
        response = self.app.delete('/api/person/1', headers=headers,
                                   content_type=content_type)
        assert response.status_code == 204

    def test_disallow_delete_many(self):
        """Tests that deleting an entire collection is disallowed by default.

        Deleting an entire collection is not discussed in the JSON API
        specification.

        """
        response = self.app.delete('/api/person')
        assert response.status_code == 405

    def test_integrity_error(self):
        """Tests that an :exc:`IntegrityError` raised in a
        :http:method:`delete` request is caught and returned to the client
        safely.

        """
        assert False, 'Not implemented'

    def test_nonexistent_instance(self):
        """Tests that a request to delete a nonexistent resource yields a
        :http:status:`404 response.

        """
        response = self.app.delete('/api/person/1')
        assert response.status_code == 404

    def test_related_resource_url(self):
        """Tests that attempting to delete from a related resource URL (instead
        of a relationship URL) yields an error response.

        """
        article = self.Article(id=1)
        self.session.add(article)
        self.session.commit()
        response = self.app.delete('/api/article/1/author')
        assert response.status_code == 405
        # TODO check error message here


class TestProcessors(ManagerTestBase):
    """Tests for pre- and postprocessors."""

    def setup(self):
        super(TestProcessors, self).setup()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode)

        self.Person = Person
        self.Base.metadata.create_all()

    def test_change_id(self):
        """Tests that a return value from a preprocessor overrides the ID of
        the resource to fetch as given in the request URL.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()

        def increment_id(resource_id=None, **kw):
            if resource_id is None:
                raise ProcessingException
            return int(resource_id) + 1

        preprocessors = dict(DELETE_RESOURCE=[increment_id])
        self.manager.create_api(self.Person, methods=['DELETE'],
                                preprocessors=preprocessors)
        response = self.app.delete('/api/person/0')
        assert response.status_code == 204
        assert self.session.query(self.Person).count() == 0

    def test_processing_exception(self):
        """Tests for a preprocessor that raises a :exc:`ProcessingException`
        when deleting a single resource.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()

        def forbidden(**kw):
            raise ProcessingException(status=403, detail='forbidden')

        preprocessors = dict(DELETE_RESOURCE=[forbidden])
        self.manager.create_api(self.Person, methods=['DELETE'],
                                preprocessors=preprocessors)
        response = self.app.delete('/api/person/1')
        assert response.status_code == 403
        document = loads(response.data)
        errors = document['errors']
        assert len(errors) == 1
        error = errors[0]
        assert 'forbidden' == error['detail']
        # Ensure that the person has not been deleted.
        assert self.session.query(self.Person).first() == person

    def test_postprocessor(self):
        """Tests that a postprocessor is invoked when deleting a resource."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()

        def assert_deletion(was_deleted=False, **kw):
            assert was_deleted

        postprocessors = dict(DELETE_RESOURCE=[assert_deletion])
        self.manager.create_api(self.Person, methods=['DELETE'],
                                postprocessors=postprocessors)
        response = self.app.delete('/api/person/1')
        assert response.status_code == 204


@skip_unless(has_flask_sqlalchemy, 'Flask-SQLAlchemy not found.')
class TestFlaskSqlalchemy(FlaskTestBase):
    """Tests for deleting resources defined as Flask-SQLAlchemy models instead
    of pure SQLAlchemy models.

    """

    def setup(self):
        """Creates the Flask-SQLAlchemy database and models."""
        super(TestFlaskSqlalchemy, self).setup()
        self.db = SQLAlchemy(self.flaskapp)
        self.session = self.db.session

        class Person(self.db.Model):
            id = self.db.Column(self.db.Integer, primary_key=True)

        self.Person = Person
        self.db.create_all()
        self.manager = APIManager(self.flaskapp, flask_sqlalchemy_db=self.db)
        self.manager.create_api(self.Person, methods=['DELETE'])

    def teardown(self):
        """Drops all tables and unregisters Flask-SQLAlchemy session signals.

        """
        self.db.drop_all()
        unregister_fsa_session_signals()

    def test_create(self):
        """Tests for deleting a resource."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.delete('/api/person/1')
        assert response.status_code == 204
        assert self.Person.query.count() == 0
