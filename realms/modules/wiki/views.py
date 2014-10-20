from flask import abort, g, render_template, request, redirect, Blueprint, flash, url_for, current_app
from flask.ext.login import login_required
from realms.lib.util import to_canonical, remove_ext
from realms.modules.wiki.models import Wiki
from realms import current_user, app

blueprint = Blueprint('wiki', __name__, url_prefix=app.config['RELATIVE_PATH'])


@app.before_request
def init_wiki():
    g.current_wiki = Wiki(app.config['WIKI_PATH'])


@blueprint.route("/_commit/<sha>/<name>")
def commit(name, sha):
    cname = to_canonical(name)

    data = g.current_wiki.get_page(cname, sha=sha)

    if not data:
        abort(404)

    return render_template('wiki/page.html', name=name, page=data, commit=sha)


@blueprint.route("/_compare/<name>/<regex('[^.]+'):fsha><regex('\.{2,3}'):dots><regex('.+'):lsha>")
def compare(name, fsha, dots, lsha):
    diff = g.current_wiki.compare(name, fsha, lsha)
    return render_template('wiki/compare.html', name=name, diff=diff, old=fsha, new=lsha)


@blueprint.route("/_revert", methods=['POST'])
@login_required
def revert():
    name = request.form.get('name')
    commit = request.form.get('commit')
    cname = to_canonical(name)
    message = request.form.get('message', "Reverting %s" % cname)

    if cname in app.config.get('WIKI_LOCKED_PAGES'):
        return dict(error=True, message="Page is locked")

    sha = g.current_wiki.revert_page(name, commit, message=message,
                                     username=current_user.username)
    if sha:
        flash("Page reverted")

    return dict(sha=sha)


@blueprint.route("/_history/<name>")
def history(name):
    return render_template('wiki/history.html', name=name, history=g.current_wiki.get_history(name))


@blueprint.route("/_edit/<name>")
@login_required
def edit(name):
    cname = to_canonical(name)
    page = g.current_wiki.get_page(name)

    if not page:
        # Page doesn't exist
        return redirect(url_for('wiki.create', name=cname))

    name = remove_ext(page['name'])
    g.assets['js'].append('editor.js')
    return render_template('wiki/edit.html',
                           name=name,
                           content=page.get('data'),
                           info=page.get('info'),
                           sha=page.get('sha'),
                           partials=page.get('partials'))


@blueprint.route("/_create/", defaults={'name': None})
@blueprint.route("/_create/<name>")
@login_required
def create(name):
    cname = to_canonical(name) if name else ""
    if cname and g.current_wiki.get_page(cname):
        # Page exists, edit instead
        return redirect(url_for('wiki.edit', name=cname))

    g.assets['js'].append('editor.js')
    return render_template('wiki/edit.html',
                           name=cname,
                           content="",
                           info={})


@blueprint.route("/_index")
def index():
    return render_template('wiki/index.html', index=g.current_wiki.get_index())


@blueprint.route("/<name>", methods=['POST', 'PUT', 'DELETE'])
@login_required
def page_write(name):
    cname = to_canonical(name)

    if not cname:
            return dict(error=True, message="Invalid name")

    if request.method == 'POST':
        # Create
        if cname in app.config.get('WIKI_LOCKED_PAGES'):
            return dict(error=True, message="Page is locked")

        sha = g.current_wiki.write_page(cname,
                                        request.form['content'],
                                        message=request.form['message'],
                                        create=True,
                                        username=current_user.username)

    elif request.method == 'PUT':
        edit_cname = to_canonical(request.form['name'])

        if edit_cname in app.config.get('WIKI_LOCKED_PAGES'):
            return dict(error=True, message="Page is locked")

        if edit_cname != cname.lower():
            g.current_wiki.rename_page(cname, edit_cname)

        sha = g.current_wiki.write_page(edit_cname,
                                        request.form['content'],
                                        message=request.form['message'],
                                        username=current_user.username)

        return dict(sha=sha)

    else:
        # DELETE
        sha = g.current_wiki.delete_page(name, user=current_user)

    return dict(sha=sha)


@blueprint.route("/", defaults={'name': 'home'})
@blueprint.route("/<name>")
def page(name):
    cname = to_canonical(name)
    if cname != name:
        return redirect(url_for('wiki.page', name=cname))

    data = g.current_wiki.get_page(cname)

    if data:
        return render_template('wiki/page.html', name=cname, page=data, partials=data.get('partials'))
    else:
        return redirect(url_for('wiki.create', name=cname))