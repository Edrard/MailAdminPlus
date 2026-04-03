# Author: Open Source Contributor
# Mail Alias Controllers

import web
import settings

from libs import iredutils, form_utils
from libs.sqllib import SQLWrap, decorators
from libs.sqllib import domain as sql_lib_domain
from libs.sqllib import admin as sql_lib_admin
from libs.sqllib import alias as sql_lib_alias

import json

session = web.config.get('_session')

class List:
    @decorators.require_global_admin
    def GET(self, domain, cur_page=1, disabled_only=False):
        domain = str(domain).lower()
        cur_page = int(cur_page) or 1

        form = web.input(_unicode=False)
        first_char = None
        if 'starts_with' in form:
            first_char = form.get('starts_with')[:1].upper()
            if not iredutils.is_valid_account_first_char(first_char):
                first_char = None

        _wrap = SQLWrap()
        conn = _wrap.conn

        total = 0
        
        qr = sql_lib_alias.get_paged_aliases(conn=conn,
                                             domain=domain,
                                             cur_page=cur_page,
                                             first_char=first_char,
                                             disabled_only=disabled_only)

        records = []
        if qr[0]:
            records = qr[1]
            total = len(records)
        else:
            raise web.seeother('/domains?msg=%s' % web.urlquote(qr[1]))

        return web.render('sql/alias/list.html',
                          cur_domain=domain,
                          cur_page=cur_page,
                          total=total,
                          aliases=records,
                          first_char=first_char,
                          disabled_only=disabled_only,
                          msg=form.get('msg', None))

    @decorators.csrf_protected
    @decorators.require_global_admin
    def POST(self, domain, page=1):
        form = web.input(_unicode=False, mail=[])
        page = int(page)
        if page < 1:
            page = 1

        domain = str(domain).lower()

        mails = [str(v).lower()
                 for v in form.get('mail', [])
                 if iredutils.is_email(v) and str(v).lower().endswith('@' + domain)]

        action = form.get('action', None)
        msg = form.get('msg', None)

        _wrap = SQLWrap()
        conn = _wrap.conn

        if action == 'delete':
            result = sql_lib_alias.delete_aliases(conn=conn, accounts=mails)
            msg = 'DELETED'
        elif action == 'enable':
            result = sql_lib_alias.set_aliases_status(conn=conn, accounts=mails, status=1)
            msg = 'ENABLED'
        elif action == 'disable':
            result = sql_lib_alias.set_aliases_status(conn=conn, accounts=mails, status=0)
            msg = 'DISABLED'
        else:
            result = (False, 'INVALID_ACTION')

        if result[0] is True:
            raise web.seeother('/aliases/%s/page/%d?msg=%s' % (domain, page, msg))
        else:
            raise web.seeother('/aliases/%s/page/%d?msg=%s' % (domain, page, web.urlquote(result[1])))

class ListDisabled(List):
    @decorators.require_global_admin
    def GET(self, domain, cur_page=1):
        return List.GET(self, domain, cur_page=cur_page, disabled_only=True)

class Profile:
    @decorators.require_global_admin
    def GET(self, profile_type, mail):
        mail = str(mail).lower()
        domain = mail.split('@', 1)[-1]

        _wrap = SQLWrap()
        conn = _wrap.conn

        form = web.input()
        msg = form.get('msg', '')

        qr = sql_lib_alias.profile(mail=mail, conn=conn)
        if qr[0]:
            alias_profile = qr[1]
        else:
            raise web.seeother('/aliases/{}?msg={}'.format(domain, web.urlquote(qr[1])))

        return web.render(
            'sql/alias/profile.html',
            cur_domain=domain,
            mail=mail,
            profile_type=profile_type,
            profile=alias_profile,
            msg=msg,
        )

    @decorators.require_global_admin
    @decorators.csrf_protected
    def POST(self, profile_type, mail):
        form = web.input()
        mail = str(mail).lower()

        _wrap = SQLWrap()
        conn = _wrap.conn

        result = sql_lib_alias.update(conn=conn,
                                      mail=mail,
                                      profile_type=profile_type,
                                      form=form)

        if result[0]:
            raise web.seeother('/profile/alias/{}/{}?msg=UPDATED'.format(profile_type, mail))
        else:
            raise web.seeother('/profile/alias/{}/{}?msg={}'.format(profile_type, mail, web.urlquote(result[1])))


class Create:
    @decorators.require_global_admin
    def GET(self, domain):
        domain = str(domain).lower()
        form = web.input()

        _wrap = SQLWrap()
        conn = _wrap.conn

        if session.get('is_global_admin'):
            qr = sql_lib_domain.get_all_domains(conn=conn, name_only=True)
        else:
            qr = sql_lib_admin.get_managed_domains(conn=conn,
                                                   admin=session.get('username'),
                                                   domain_name_only=True)

        if qr[0] is True:
            all_domains = qr[1]
        else:
            raise web.seeother('/domains?msg=' + web.urlquote(qr[1]))

        qr_profile = sql_lib_domain.simple_profile(domain=domain, conn=conn)
        if qr_profile[0] is True:
            domain_profile = qr_profile[1]
        else:
            raise web.seeother('/domains?msg=%s' % web.urlquote(qr_profile[1]))

        return web.render(
            'sql/alias/create.html',
            cur_domain=domain,
            allDomains=all_domains,
            profile=domain_profile,
            msg=form.get('msg'),
        )

    @decorators.csrf_protected
    @decorators.require_global_admin
    def POST(self, domain):
        domain = str(domain).lower()
        form = web.input()

        domain_in_form = form_utils.get_domain_name(form)
        if domain != domain_in_form:
            raise web.seeother('/domains?msg=PERMISSION_DENIED')

        username = form_utils.get_single_value(form,
                                               input_name='username',
                                               to_string=True).lower()

        qr = sql_lib_alias.add_alias_from_form(domain=domain, form=form)

        if qr[0]:
            raise web.seeother('/profile/alias/general/{}@{}?msg=CREATED'.format(username, domain))
        else:
            raise web.seeother('/create/alias/{}?msg={}'.format(domain, web.urlquote(qr[1])))

class SearchDestinations:
    @decorators.require_global_admin
    def GET(self):
        form = web.input()
        query = form.get('q', '').strip()
        
        _wrap = SQLWrap()
        conn = _wrap.conn
        
        qr = sql_lib_alias.get_destinations_by_query(conn, query)
        web.header('Content-Type', 'application/json')
        if qr[0]:
            return json.dumps(qr[1])
        else:
            return json.dumps([])
