# Author: Open Source Contributor
# Mail Alias Database Operations

import web
import settings

from libs import iredutils, form_utils
from libs.logger import logger, log_activity
from libs.sqllib import SQLWrap, decorators, sqlutils
from libs.sqllib import general as sql_lib_general
from libs.sqllib import domain as sql_lib_domain
from libs.sqllib import admin as sql_lib_admin

session = web.config.get('_session', {})

@decorators.require_global_admin
def get_paged_aliases(conn,
                      domain,
                      cur_page=1,
                      first_char=None,
                      disabled_only=False):
    domain = str(domain).lower()
    cur_page = int(cur_page) or 1

    sql_vars = {'domain': domain}
    sql_where = 'domain=$domain'

    if first_char:
        sql_where += ' AND address LIKE %s' % web.sqlquote(first_char.lower() + '%')

    if disabled_only:
        sql_where += ' AND active=0'

    try:
        qr = conn.select(
            'alias',
            vars=sql_vars,
            what='address, domain, name, expired, active, created',
            where=sql_where,
            order='address ASC',
            limit=settings.PAGE_SIZE_LIMIT,
            offset=(cur_page - 1) * settings.PAGE_SIZE_LIMIT)

        return (True, list(qr))
    except Exception as e:
        return (False, repr(e))

def add_alias_from_form(domain, form, conn=None):
    mail_domain = form_utils.get_domain_name(form)
    if mail_domain:
        mail_domain = mail_domain.lower()

    mail_username = form.get('username')
    if mail_username:
        mail_username = web.safestr(mail_username).strip().lower()
    else:
        return (False, 'INVALID_ACCOUNT')

    address = mail_username + '@' + mail_domain

    if mail_domain != domain:
        return (False, 'PERMISSION_DENIED')

    if not iredutils.is_email(address):
        return (False, 'INVALID_MAIL')

    if not conn:
        _wrap = SQLWrap()
        conn = _wrap.conn

    if sql_lib_general.is_email_exists(mail=address, conn=conn):
        return (False, 'ALREADY_EXISTS')

    destinations_str = form.get('destinations', '')
    if not destinations_str:
        return (False, 'EMPTY_DESTINATIONS')

    raw_destinations = [x.strip().lower() for x in destinations_str.replace('\n', ',').replace(' ', ',').split(',')]
    destinations = [x for x in raw_destinations if iredutils.is_email(x)]

    if not destinations:
        return (False, 'INVALID_DESTINATION_MAIL')

    cn = form_utils.get_single_value(form, input_name='cn', default_value='')

    try:
        conn.insert('alias',
                    address=address,
                    domain=domain,
                    name=cn,
                    created=iredutils.get_gmttime(),
                    active=1)

        for dest in set(destinations):
            dest_domain = dest.split('@', 1)[-1]
            conn.insert('forwardings',
                        address=address,
                        forwarding=dest,
                        domain=domain,
                        dest_domain=dest_domain,
                        is_list=1,
                        active=1)

        log_activity(msg="Create mail alias: %s -> %s." % (address, ', '.join(set(destinations))),
                     domain=domain,
                     event='create')
        return (True, )
    except Exception as e:
        return (False, repr(e))

def delete_aliases(accounts, conn=None):
    accounts = [str(v).lower() for v in accounts if iredutils.is_email(v)]

    if not accounts:
        return (True, )

    if not conn:
        _wrap = SQLWrap()
        conn = _wrap.conn

    try:
        sql_vars = {'accounts': accounts}
        conn.delete('alias', vars=sql_vars, where='address IN $accounts')
        conn.delete('forwardings', vars=sql_vars, where='address IN $accounts')

        domain = accounts[0].split('@', 1)[-1]
        log_activity(event='delete',
                     domain=domain,
                     msg="Delete mail alias: %s." % ', '.join(accounts))

        return (True, )
    except Exception as e:
        return (False, repr(e))

def profile(mail, conn=None):
    mail = str(mail).lower()
    try:
        if not conn:
            _wrap = SQLWrap()
            conn = _wrap.conn

        qr = conn.select('alias', vars={'mail': mail}, where='address=$mail', limit=1)
        if not qr:
            return (False, 'NO_SUCH_ACCOUNT')
        
        alias_profile = qr[0]

        qr_fwds = conn.select('forwardings', vars={'mail': mail}, what='forwarding, active', where='address=$mail', order='forwarding ASC')
        forwardings = list(qr_fwds)

        alias_profile['forwardings'] = forwardings
        return (True, alias_profile)
    except Exception as e:
        return (False, repr(e))

def update(conn, mail, profile_type, form):
    mail = str(mail).lower()
    domain = mail.split('@', 1)[-1]

    if profile_type == 'general':
        action = form.get('action', '')
        
        if action == 'add_forwarding':
            destinations_str = form.get('destinations', '')
            raw_destinations = [x.strip().lower() for x in destinations_str.replace('\n', ',').replace(' ', ',').split(',')]
            destinations = [x for x in raw_destinations if iredutils.is_email(x)]
            
            if not destinations:
                return (False, 'INVALID_DESTINATION_MAIL')

            try:
                for dest in set(destinations):
                    dest_domain = dest.split('@', 1)[-1]
                    
                    existing = conn.select('forwardings', vars={'addr': mail, 'fwd': dest}, where='address=$addr AND forwarding=$fwd')
                    if not list(existing):
                        conn.insert('forwardings',
                                    address=mail,
                                    forwarding=dest,
                                    domain=domain,
                                    dest_domain=dest_domain,
                                    is_list=1,
                                    active=1)
                log_activity(msg="Update alias %s: added destinations." % mail, domain=domain, event='update')
                return (True, {})
            except Exception as e:
                return (False, repr(e))
                
        elif action == 'delete_forwarding':
            dest_to_delete = form.get('forwarding', '').lower()
            if not dest_to_delete:
                return (False, 'INVALID_DESTINATION_MAIL')
            try:
                conn.delete('forwardings', vars={'addr': mail, 'fwd': dest_to_delete}, where='address=$addr AND forwarding=$fwd')
                log_activity(msg="Update alias %s: removed destination %s." % (mail, dest_to_delete), domain=domain, event='update')
                return (True, {})
            except Exception as e:
                return (False, repr(e))
                
        else:
            updates = {}
            updates['name'] = form.get('cn', '')

            updates['active'] = 0
            if 'accountStatus' in form:
                updates['active'] = 1

            try:
                conn.update('alias',
                            vars={'address': mail},
                            where='address=$address',
                            **updates)
                
                conn.update('forwardings',
                            vars={'address': mail},
                            where='address=$address',
                            active=updates['active'])

                log_activity(msg="Update mail alias profile: %s." % mail,
                             admin=session.get('username'),
                             username=mail,
                             domain=domain,
                             event='update')

                return (True, {})
            except Exception as e:
                return (False, repr(e))

    return (True, {})

def set_aliases_status(conn, accounts, status):
    accounts = [str(v).lower() for v in accounts if iredutils.is_email(v)]
    if not accounts:
        return (True, )

    try:
        sql_vars = {'accounts': accounts, 'status': status}
        conn.update('alias', vars=sql_vars, where='address IN $accounts', active=status)
        conn.update('forwardings', vars=sql_vars, where='address IN $accounts', active=status)

        domain = accounts[0].split('@', 1)[-1]
        action_str = 'Enable' if status == 1 else 'Disable'
        log_activity(event='update', domain=domain, msg="%s mail aliases: %s." % (action_str, ', '.join(accounts)))

        return (True, )
    except Exception as e:
        return (False, repr(e))

def get_destinations_by_query(conn, query, limit=10):
    query = str(query).lower().strip()
    if not query:
        return (True, [])
        
    sql_where = "address LIKE $q OR forwarding LIKE $q"
    sql_vars = {'q': '%' + query + '%'}
    
    try:
        qr1 = conn.select('forwardings', vars=sql_vars, what='DISTINCT address AS mail', where=sql_where, limit=limit)
        qr2 = conn.select('forwardings', vars=sql_vars, what='DISTINCT forwarding AS mail', where=sql_where, limit=limit)
        
        matches = set()
        for r in list(qr1) + list(qr2):
            if r.mail:
                matches.add(r.mail.lower())
                
        return (True, sorted(list(matches))[:limit])
    except Exception as e:
        return (False, repr(e))
