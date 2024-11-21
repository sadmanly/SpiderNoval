from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, RadioField
from wtforms.validators import DataRequired, Optional


class SearchForm(FlaskForm):
    search_type = RadioField("搜索类型", choices=[("name", "按书名搜索"), ("author", "按作者搜索")], default="name")
    search_name = StringField("书名", validators=[Optional()])
    author_name = StringField("作者名", validators=[Optional()])
    submit = SubmitField("搜索")