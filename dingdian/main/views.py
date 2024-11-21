from flask import flash, render_template, url_for, redirect, request, current_app, jsonify
from flask.blueprints import Blueprint
from concurrent.futures import ThreadPoolExecutor

from dingdian import db
from .forms import SearchForm
from ..spider.spider import DdSpider
from ..models import Novel, Chapter, Article
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta



main = Blueprint('main', __name__)

@main.errorhandler(404)
def page_not_found(error):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'not found'})
        response.status_code = 404
        return response
    return render_template('404.html'), 404

@main.errorhandler(500)
def internal_server_error(error):
    return render_template('500.html'), 500

@main.route('/', methods=['GET', 'POST'])
@main.route('/index', methods=['GET', 'POST'])
def index():
    form = SearchForm()
    if form.validate_on_submit():
        search_type = form.search_type.data
        search_name = form.search_name.data
        author_name = form.author_name.data
        if search_type == "author":
            search_name = author_name
        
        flash('搜索成功。')
        return redirect(url_for('main.result', search=search_name,search_type = search_type))
    return render_template('index.html', form=form)

@main.route('/results/<search>/<search_type>')
def result(search,search_type):
    page = request.args.get('page', 0, type=int)
    books = []
    # 查找数据库中search键相等的结果，如果有则不需要调用爬虫，直接返回
    if search_type == "author":
        books = Novel.query.filter_by(author=search, page=page).all()
    else:
        books = Novel.query.filter_by(search_name=search, page=page).all()
    if books:
        return render_template('result.html', search=search, page=page, books=books)
    spider = DdSpider()

    for data in spider.get_index_result(search,search_type, page):
        novel = Novel(book_name=data['book_name'],
                    book_url=data['book_url'],
                    author=data['author'],
                    book_type=data['book_type'],
                    update_time=data['update_time'],
                    page=page,
                    search_name=search)
        db.session.add(novel)
    books = Novel.query.filter_by(search_name=search, page=page).all()

    return render_template('result.html', search=search,search_type=search_type, page=page, books=books)

@main.route('/chapter/<int:book_id>')
def chapter(book_id):
    page = request.args.get('page', 1, type=int)
    all_chapter = Chapter.query.filter_by(book_id=book_id).first()
    # print(type(pagination))
    per_page=current_app.config['CHAPTER_PER_PAGE']

    if all_chapter:
        pagination = Chapter.query.filter_by(book_id=book_id).paginate(
                page=page, per_page=per_page,
                error_out=False
        )
        chapters = pagination.items
        book = Novel.query.filter_by(id=book_id).first()
        return render_template('chapter.html', book=book, chapters=chapters, pagination=pagination)

    spider = DdSpider()
    book = Novel.query.filter_by(id=book_id).first()
    datas = spider.get_chapter(book.book_url)

    for data in datas:
        chapter = Chapter(chapter=data['chapter'],
                           chapter_url=data['url'],
                           book_id=book_id)
        db.session.add(chapter)    
        db.session.flush()
        article2 = Article(content=data['content'],chapter_id=chapter.id)
        db.session.add(article2)

    db.session.commit()
    pagination2 = Chapter.query.filter_by(book_id=book_id).paginate(
        page=page, per_page=per_page,
        error_out=False
    )

    chapters = pagination2.items

    return render_template('chapter.html', book=book, chapters=chapters, pagination=pagination2)

@main.route('/content/<int:chapter_id>')
def content(chapter_id):
    book_id = Chapter.query.filter_by(id=chapter_id).first().book_id
    article = Article.query.filter_by(chapter_id=chapter_id).first()
    if article:
        chapter = Chapter.query.filter_by(id=chapter_id).first()
        return render_template('article.html', chapter=chapter, article=article, book_id=book_id)

    spider = DdSpider()
    chapter = Chapter.query.filter_by(id=chapter_id).first()
    article2 = Article(content=spider.get_article(chapter.chapter_url),
                      chapter_id=chapter_id)
    db.session.add(article2)
    return render_template('article.html', chapter=chapter, article=article2, book_id=book_id)

# 下一章
@main.route('/next/<int:chapter_id>')
def next(chapter_id):
    chapter = Chapter.query.filter_by(id=chapter_id).first()
    book = Novel.query.filter_by(id=chapter.book_id).first()
    # print(type(all_chapters))
    all_chapters = [i for i in book.chapters]
    # all_chapters是一个集合,通过操作数组很容易拿到下一章内容
    if all_chapters[-1] != chapter:
        next_chapter = all_chapters[all_chapters.index(chapter)+1]
        return redirect(url_for('main.content', chapter_id=next_chapter.id))
    else:
        flash('已是最后一章了。')
        return redirect(url_for('main.content', chapter_id=chapter_id))

# 上一章
@main.route('/prev/<int:chapter_id>')
def prev(chapter_id):
    chapter = Chapter.query.filter_by(id=chapter_id).first()
    book = Novel.query.filter_by(id=chapter.book_id).first()
    all_chapters = [i for i in book.chapters]
    if all_chapters[0] != chapter:
        prev_chapter = all_chapters[all_chapters.index(chapter)-1]
        return redirect(url_for('main.content', chapter_id=prev_chapter.id))
    else:
        flash('没有上一章了哦。')
        return redirect(url_for('main.content', chapter_id=chapter_id))

