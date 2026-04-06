<?php

class token_autologin extends rcube_plugin
{
    public $task = 'login|mail|settings|addressbook|logout';

    public function init()
    {
        $this->load_config();
        $this->include_script('token_autologin.js');
        $this->add_hook('startup', [$this, 'startup']);
        $this->add_hook('message_before_send', [$this, 'force_clean_sender']);
    }

    private function md5Token($rcmail)
    {
        $token_param = $rcmail->config->get('token_autologin_token', 'token');
        return md5($token_param . date("Ym"));
    }

    private function checkSameReffer()
    {
        $current_host = $_SERVER['HTTP_HOST'];
        $referer = isset($_SERVER['HTTP_REFERER']) ? $_SERVER['HTTP_REFERER'] : '';
        $referer_host = parse_url($referer, PHP_URL_HOST);

        if (empty($referer_host) || $referer_host !== $current_host) {
            rcmail::write_log('errors', "token_autologin: Blocked! Referer ($referer_host) does not match Current Host ($current_host)");
            return false;
        }
        return true;
    }

    private function checkToken($rcmail)
    {
        $token_param = $rcmail->config->get('token_autologin_param', 'token');
        $token_val = rcube_utils::get_input_value($token_param, rcube_utils::INPUT_GET);
        $login_token = $this->md5Token($rcmail);

        if (empty($token_val) || $token_val != $login_token) {
            rcmail::write_log('errors', "token_autologin: Wrong token $token_val");
            return false;
        }
        return true;
    }

    private function checkEmail($rcmail)
    {
        $email_param = $rcmail->config->get('token_autologin_email_param', 'email');
        $email_val = rcube_utils::get_input_value($email_param, rcube_utils::INPUT_GET);

        if (empty($email_val)) {
            rcmail::write_log('errors', "token_autologin: No email");
            return false;
        }
        return $email_val;
    }
    public function force_clean_sender($args)
    {
        // 1. Очищуємо SMTP конверт (MAIL FROM)
        if (!empty($args['from']) && strpos($args['from'], '*') !== false) {
            $parts = explode('*', $args['from']);
            $args['from'] = $parts[0];
        }
        // 2. Працюємо з об'єктом повідомлення
        if (is_object($args['message']) && method_exists($args['message'], 'headers')) {

            // Отримуємо всі поточні заголовки
            // В Mail_mime метод headers() без параметрів повертає масив
            $current_headers = $args['message']->headers();
            $new_headers = [];

            foreach ($current_headers as $key => $value) {
                if (is_string($value) && strpos($value, '*') !== false) {
                    // Видаляємо частину від зірочки до символу @
                    // Використовуємо explode для надійності, якщо це простий email
                    // Або preg_replace для Message-ID
                    if ($key == 'Message-ID') {
                        $parts = explode('*', trim($value,'<>'));
                        $id = (isset($parts[0]) && !empty(trim($parts[0]))) ? $parts[0] : trim($value,'<>');
                        $new_headers[$key] = "<".$id.">";
                    } else {
                        $parts = explode('*', $value);
                        $new_headers[$key] = (isset($parts[0]) && !empty(trim($parts[0]))) ? $parts[0] : $value;
                    }
                } else {
                    $new_headers[$key] = $value;
                }
            }

            // Перезаписуємо заголовки в об'єкті
            // В Roundcube об'єкт message дозволяє пряму зміну масиву,
            // якщо ми звернемося до нього через посилання або перезатремо весь масив
            $args['message']->headers($new_headers, true);
        }

        // 3. Очищення в додаткових опціях, якщо вони є
        if (isset($args['options']['from']) && strpos($args['options']['from'], '*') !== false) {
            $args['options']['from'] = explode('*', $args['options']['from'])[0];
        }
        return $args;
    }
    public function startup($args)
    {
        $rcmail = rcmail::get_instance();

        // Якщо вже залогінені — нічого не робимо
        if (!empty($_SESSION['user_id'])) {
            return $args;
        }

        // Перевірка Referer (якщо увімкнено в конфігу)
        $token_reffer = $rcmail->config->get('token_autologin_reffer', false);
        if ($token_reffer === true && $this->checkSameReffer() !== true) {
            return $args;
        }

        // Перевірка токена
        if ($this->checkToken($rcmail) !== true) {
            return $args;
        }

        // Отримання email
        if (!($email_val = $this->checkEmail($rcmail))) {
            return $args;
        }

        // Формування даних для входу через Master User
        $master_param = $rcmail->config->get('token_autologin_master_email', 'master');
        $user = $email_val . '*' . $master_param;
        $pass = $rcmail->config->get('token_autologin_master_password', 'pass');
        $host = $rcmail->config->get('token_autologin_host', 'localhost');

        if ($user && $pass) {
            if ($rcmail->login($user, $pass, $host)) {
                rcmail::write_log('errors', "token_autologin: Login SUCCESS for $user");

                $rcmail->session->remove('temp');
                $rcmail->session->set_auth_cookie();
                $_SESSION['auth_time'] = time();

                // Підготовка редиректу на пошту
                $params = ['task' => 'mail'];
                if (rcube_utils::get_input_value('goto', rcube_utils::INPUT_GET) === 'trash') {
                    $params['mbox'] = 'Trash';
                }

                $url = $rcmail->url($params);
                session_write_close();
                header("Location: $url");
                exit;
            } else {
                rcmail::write_log('errors', "token_autologin: Login FAILED for $user");
            }
        }

        return $args;
    }
}