import datetime

import bson
import gridfs
import motor
from elasticsearch import Elasticsearch
from slugify import slugify
from tornado import gen, ioloop, web
from wtforms.fields import TextAreaField, TextField
from wtforms.validators import Required
from wtforms_tornado import Form

# creating databases
db = motor.MotorClient().tornado_db
gridfs_coll = motor.MotorGridFS(db)
es = Elasticsearch()

class HomeHandler(web.RequestHandler):
    async def get(self):
        entries = []
        cursor = db.test_collection.find()
        for doc in await cursor.sort("time", -1).to_list(20):
            entries.append(doc)
        self.render("home.html", entries=entries)

class SearchHandler(web.RequestHandler):
    async def get(self):
        self.render('search.html', response=None)

    @gen.coroutine
    def post(self):
        q = self.get_argument("q")
        if q is not None:
            search_object = {"query": {'multi_match': {
                "query": q, "fields": ["title", "news"]}}}
            resp = es.search(index='news', doc_type='article', filter_path=[
                'hits.hits._source.title', 'hits.hits._source.news', 'hits.hits._source.slug'], body=search_object)
        self.render('search.html', response=resp)

class ArticleHandler(web.RequestHandler):
    async def get(self, slug):
        news_list = []
        article = db.test_collection.find({"slug": slug})
        for document in await article.to_list(1):
            news_list.append(document)
        self.render('article.html', article=news_list)

# form with validation
class SumForm(Form):
    title = TextField('title', validators=[Required()])
    body = TextAreaField('body', validators=[Required()])

# function to add article in db
@gen.coroutine
def post_func(db, es, gridfs_coll, title, body, picture):
    created = datetime.datetime.now()
    # image processing in gridfs
    gridin = yield gridfs_coll.new_file(content_type=picture.content_type)
    picture_id = gridin._id
    yield gridin.write(picture.body)
    yield gridin.close()

    # slug generator
    slug = slugify(title)
    e = db.test_collection.find({'slug': slug})
    slug_db = yield e.to_list(length=1)
    if slug_db:
        slug += "-2"

    document = {'title': title,
                'news': body,
                'time': created,
                'slug': slug,
                'picture': picture_id,
                }
    es_document = {'title': title,
                   'news': body,
                   'slug': slug
                   }
    db.test_collection.insert_one(document)
    es.index(index='news', doc_type='article', body=es_document)
    
class UploadHandler(web.RequestHandler):
    def get(self):
        self.render('upload.html')

    @gen.coroutine
    def post(self):
        form = SumForm(self.request.arguments)
        if form.validate():
            title = self.get_argument('title')
            body = self.get_argument('body')
            picture = self.request.files['file'][0]
            yield post_func(db, es, gridfs_coll, title, body, picture)        
            self.redirect("/")
        else:
            self.write("" % form.errors)

class ShowImageHandler(web.RequestHandler):
    @gen.coroutine
    def get(self, img_id):
        try:
            gridout = yield gridfs_coll.get(bson.objectid.ObjectId(img_id))
        except (bson.errors.InvalidId, gridfs.NoFile):
            raise web.HTTPError(404)
        self.set_header('Content-Type', gridout.content_type)
        self.set_header('Content-Length', gridout.length)
        yield gridout.stream_to_handler(self)


app = web.Application([
    web.url(r'/', HomeHandler),
    web.url(r'/upload', UploadHandler, name='upload'),
    web.url(r'/imgs/([\w\d]+)', ShowImageHandler, name='show_image'),
    web.url(r'/article/([^/]+)', ArticleHandler, name='article'),
    web.url(r'/search', SearchHandler, name='search'),
], debug=True)


app.listen(8000)
ioloop.IOLoop.instance().start()
