import datetime
import json
import logging
import sys
import threading
import traceback

from PyQt5 import QtCore

from utils import *
import time
from collections import namedtuple
import requests

# список токенов
TOKEN = [""]
# id устройства
DEVID = "fa39199d-63eb-44e1-9974-39cad49c4a29"
# имя устройства
DEVIC = "Xiaomi Redmi 5 Plus"
# канал/чат в телеге для логов, @домен или -ид
CHANN = ''
# токен бота в телеге для логов
TGBOT = ''
# прокси для бота. None чтобы выключить
PROXY = 'socks5://socksuser:8X5tjtV5ISNv2@alttg.proxy.mediatube.xyz:433'
POSIT = '✅'
NEGAT = '❌'
logger = logging.getLogger("clever_battle")
if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    f = logging.Formatter("[%(levelname)s] %(asctime)-15s (%(funcName)s) %(message)s")
    ch.setFormatter(f)
    logger.addHandler(ch)
    logger.info("early bootstrap")
    print(logger.handlers)
Opponent = namedtuple("Opponent", "id name photo")
Question = namedtuple("Question", "ind text answers")
GameState = namedtuple("GameState", "score opp_score opp_ind correct correct_ind")
FinishState = namedtuple("FinishState", "id winner coins bet returned score opp_score early bot_won")
Action = namedtuple("ThreadAction", "type data")


class TGThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

    def run(self):
        pass

    def send(self, type, text):
        self.lock.acquire()
        try:
            logger.info("sending tg to " + CHANN)
            r = requests.post(
                "https://api.telegram.org/bot" + TGBOT + "/sendMessage",
                json=dict(chat_id=CHANN, text="**Уведомление типа** #{ty}:\n{t}".format(t=text, ty=type),
                          parse_mode='markdown'),
                proxies=({"http": PROXY, "https": PROXY} if PROXY is not None else {}))
            logger.debug("tg response: " + str(r.json()))
            r.raise_for_status()
            j = json.loads(r.text)
            logger.info("sent to telegram")
        except:
            logger.warning("failed to send to telegram: {}".format(traceback.format_exc()))
        self.lock.release()


class Thread(QtCore.QThread):
    event = QtCore.pyqtSignal(Action)

    def __init__(self, n, token=TOKEN, tg=False):
        super().__init__()
        self.n = n
        self.cgid = 0
        self.api = ApiHelper(token)
        self.tg = tg
        self.last_started = 0
        self.started = 0
        self.points_per_session = 0
        if tg:
            self.tg_thread = TGThread()
            self.tg_thread.start()

    def run(self):
        if not self._check_auth():
            self._emit_and_send(Action("stop", {"reason": "invalid_token"}))
        self.started = time.time()
        if self.n == -1:
            i = 1
            while True:
                self._run_once(i, "∞")
                i += 1
        else:
            for o in range(self.n):
                self._run_once(o, self.n)
            self.event.emit(Action("stop", {"reason": "end"}))
            self.terminate()

    def _emit_and_send(self, act: Action):
        self.event.emit(act)
        if self.tg:
            self.tg_thread.send(act.type, act.data.get('data', act.data.get('reason', "")))

    def stop(self, rea='gently'):
        r = self._finish_game(self.cgid)
        self._emit_and_send(Action("state", {'data': "Игра `{r.id}` завершена. Победил vk.com/{r.winner}.\n"
                                                     "Клеверсов: `{r.coins}`, ставка: `{r.bet}`, вернул `{r.returned}`\n"
                                                     "Счет: `{r.score}:{r.opp_score}`\n"
                                                     "Вы выиграли: {r.bot_won}".format(r=r)}))
        self._emit_and_send(Action("stop", {"reason": rea}))
        self.terminate()

    def _run_once(self, n=1, m=1):
        try:
            self.last_started = time.time()
            logger.info("Начало игры {}/{}".format(n, m))
            logger.info("Запрос игры..")
            game_id = self._start_game_polling()
            self.cgid = game_id
            logger.info("Оппонент найден")
            game = self._start_game(game_id)
            logger.info("Игра запущена")
            opponent = self._get_opponent()
            logger.info("Оппонент: vk.com/id{o.id} - {o.name}".format(o=opponent))
            self._emit_and_send(Action('start', {
                'data': "Запущена игра против [{name}](vk.com/id{id})\n"
                        "Игра в сессии: `{n}/{m}`\n"
                        "Кол-во вопросов: {qcnt}, время начала: `{strt}`\n"
                        "Тип игры: `{type}`, тема: {topic}".format(
                    name=opponent.name,
                    id=opponent.id, n=n, m=m, qcnt=game["questions_count"],
                    strt=datetime.datetime.utcfromtimestamp(game["time"]).replace(tzinfo=datetime.timezone.utc).astimezone(
            tz=None).strftime("%H:%M:%S.%f"), type=game["type"], topic=game["topic_id"]
                )
            }))
            finished = False
            while not finished:
                finished, q = self._get_question(game_id)
                if q is None:
                    break
                logger.info("Получен вопрос {o.ind}: {o.text}".format(o=q))
                self._emit_and_send(Action("ans", {"data": 'Вопрос ' + str(q.ind) + ': ' +
                                                           q.text + '\n' + "\n".join(["`[{i}]` {a}".format(i=i, a=ans)
                                                                                      for i, ans in
                                                                                      enumerate(q.answers)])}))
                b = self._check_in_bd(q)
                if b is not None:
                    ans = b
                    logger.info("Вопрос найден в базе данных, отвечаю по готовым данным")
                else:
                    logger.warning("Отвечаю 1 т.к. не знаю правильного ответа")
                    ans = 1
                if self._send_answer(game_id, q.ind, ans):
                    logger.info("Ответ отправлен: {}".format(ans))
                state = self._start_check_polling()
                if state is None:
                    self._emit_and_send(Action("", {'data': ""}))
                    break
                self._emit_and_send(Action("state", {'data': "Счет: `{s.score}:{s.opp_score}`\n"
                                                             "Ответы: {ans}:{s.opp_ind}\n"
                                                             "Правильно: {corr} (`{s.correct_ind}`)\n"
                                                             "Вопрос новый: {new}"
                                           .format(s=state, ans=ans, new=POSIT if b is None else NEGAT,
                                                   corr=POSIT if state.correct else NEGAT)}))
                if b is None:
                    logger.debug("Запись в бд..")
                    self._add_to_bd(q.text, q.answers[state.correct_ind])
            r = self._finish_game(game_id)
            end = time.time()
            self._emit_and_send(Action("end", {'data': "Игра `{r.id}` завершена за {t}.\n Победил vk.com/{r.winner}.\n"
                                                       "Клеверсов: `{r.coins}`, ставка: `{r.bet}`, вернул `{r.returned}`\n"
                                                       "Счет: `{r.score}:{r.opp_score}`\n"
                                                       "Вы выиграли: {won}".format(
                r=r, t=str(datetime.timedelta(seconds=round(end - self.last_started))),
                won=POSIT if r.bot_won else NEGAT + " #loss")}))
            p, t = self._get_points()
            self.points_per_session += r.score
            self._emit_and_send(Action("stats", data={'data': "Очков за сеанс/всего: `{per_sess}/{points}`\n"
                                                              "Вы в топе: `{top}`\n"
                                                              "Работает уже `{wk}`\n"
                                                              "В среднем: `{avg} очк/ч`\n"
                                                              "В базе: `{db} вопросов`"
                                       .format(points=p, top=POSIT if t else NEGAT, per_sess=self.points_per_session,
                                               avg=round(self.points_per_session / (end - self.started) * 3600),
                                               wk=str(datetime.timedelta(seconds=round(end - self.started))),
                                               db=Database().query("SELECT COUNT(*) FROM questions")[0]['COUNT(*)'])}))
        except KeyboardInterrupt:
            self.stop('interrupted')

    def _get_points(self):
        r = self.api.execute.getStartData(need_leaderboard=1, func_v=11)["response"]["battle_leaderboards"][
            "leaderboards"]
        t = False
        for lb in r:
            for s in lb["scores"]:
                if s["user_id"] == self.user_id:
                    t = True
                    break
            if t:
                break
        return r[0]["user_score"], t

    @staticmethod
    def _check_in_bd(question: Question):
        r = Database().query("SELECT * FROM questions WHERE q LIKE '%{}%' COLLATE NOCASE".format(question.text.
                                                                                                 replace("'", "''")))
        if len(r) > 0:
            r = r[0]
            corr = r["corr"].lower()
            if corr in map(str.lower, question.answers):
                return list(map(str.lower, question.answers)).index(corr)
        return None

    @staticmethod
    def _add_to_bd(text: str, correct: str):
        try:
            Database().query("INSERT INTO questions VALUES (null, ?, ?)", text, correct)
        except sqlite3.IntegrityError:
            pass

    def _finish_game(self, id):
        while True:
            r = self.api.execute.finishGame(func_v=2, game_id=id, device_id=DEVID)
            if r.get("error", None) is not None:
                if r["error"]["error_code"] == -100:
                    continue
                logger.warning("ошибка при завершении игры: {!r}".format(r["error"]))
                return FinishState(-1, -1, -1, -1, -1, -1, -1, False, False)
            r = r.get("response", r)
            if not r["finish"]:
                logger.debug("ожидание оппонента")
                time.sleep(0.5)
                continue
            else:
                r = r["finish"]
                return FinishState(r['game_id'], r.get("winner_id", -1), r.get("coins", 0), r.get("bet", 0),
                                   r.get("coins_returned", 0), r.get("user_score", 0), r.get("opponent_score", 0),
                                   r.get("is_early", False), r.get("winner_id", -1) == self.user_id)

    def _start_check_polling(self):
        while True:
            r = self.api.streamQuiz.anytimeCheckAnswer()
            # logger.debug(r)
            if r.get("error", {"error_code": -1})["error_code"] == 2203:
                logger.debug("ожидание оппонента")
                time.sleep(0.5)
                continue
            elif r.get("error", {"error_code": -1})["error_code"] == 2204:
                logger.debug("оппонент вылетел")
                return None
            elif r.get("error", {"error_code": -1})["error_code"] == 2206:
                logger.debug("вы вылетели")
                return None
            elif r.get("error", {"error_code": -1})["error_code"] == -100:
                continue
            r = r["response"]
            return GameState(r.get("total_score", 0), r.get("opponent_score", 0), r.get("opponent_answer_id", -1),
                             r.get("is_correct"), r.get("right_answer_id", -1))

    def _send_answer(self, gameid, qind, ansind):
        return bool(self.api.streamQuiz.anytimeSendAnswer(game_id=gameid, question_ind=qind, answer_id=ansind))

    def _get_question(self, id):
        while True:
            r = self.api.streamQuiz.anytimeGetNextQuestion(is_realtime=1, game_id=id)
            # logger.debug(r)
            if r.get("error", {"error_code": -1})["error_code"] == 2203:
                logger.debug("ожидание оппонента")
                time.sleep(0.5)
                continue
            elif r.get("error", {"error_code": -1})["error_code"] == 2204:
                logger.error("у оппонента проблемы, отмена..")
                return True, None
            elif r.get("error", {"error_code": -1})["error_code"] == 2206:
                logger.debug("у вас проблемы, отмена..")
                return True, None
            elif r.get("error", {"error_code": -1})["error_code"] == -100:
                continue
            elif r.get("error", {"error_code": -1})["error_code"] == 6:
                continue
            r = r["response"]
            return r['is_last'], Question(r['ind'], r['text'],
                                          [a['text'] for a in sorted(r['answers'], key=lambda x: x['id'])])

    def _start_game(self, id):
        while True:
            r = self.api.streamQuiz.anytimeStartGame(is_realtime=1, game_id=id, device_id=DEVID)
            logger.debug(r)
            if r.get("error", None) is not None:
                continue
            return r["response"]

    def _get_opponent(self):
        while True:
            r = self.api.execute.getBattleGameState(device_id=DEVID)
            logger.debug(r)
            if r.get("error", None) is not None:
                continue
            r = r["response"]["opponent"]
            return Opponent(r["id"], r["first_name"] + " " + r["last_name"], r["photo_100"])

    def _start_game_polling(self):
        found = 0
        while not found:
            try:
                r = self.api.execute.pollRandomGame()
            except CaptchaNeededError:
                logger.warning("попытка обхода капчи ожиданием..")
                time.sleep(10)
                continue
            logger.debug(r)
            if r.get("error", {"error_code": -1})["error_code"] == 2214:
                logger.warning("Игра уже запущена на аккаунте, жду 15 секунд")
                time.sleep(15)
                continue
            elif r.get("error", {"error_code": -1})["error_code"] == -100:
                continue
            if r["response"] != 1:
                found = r["response"]
            else:
                time.sleep(0.5)
        return found

    def _check_auth(self):
        try:
            r = self.api.users.get()
            # logger.debug(r)
            self.user_id = r["response"][0]["id"]
            return True
        except ValueError:
            print("Неверный токен!")
            return False
        except CaptchaNeededError as e:
            self._request_captcha(e.img, e.retry)

    def _request_captcha(self, img, retry):
        d = requests.get(img).content
        self.event.emit(Action("captcha", {"data": d, "retry": retry}))


class LearningThread(QtCore.QThread):
    __slots__ = ['api']
    event = QtCore.pyqtSignal(Action)

    def __init__(self):
        super().__init__()
        self.api = ApiHelper()

    def run(self):
        logger.info("Начало обучения..")
        r = self.api.execute.getTrainQuestions()
        for q in r["response"]["questions"]:
            self._add_to_bd(q["text"], q["answers"][q["right_answer_id"]]["text"])
            logger.debug("в бд добавлен вопрос {}".format(q["text"]))
        logger.info("Обучение завершено")
        self.event.emit(Action("learning_end", None))

    @staticmethod
    def _add_to_bd(text: str, correct: str):
        try:
            Database().query("INSERT INTO questions VALUES (null, ?, ?)", text, correct)
        except sqlite3.IntegrityError:
            pass


class ConsoleApp(QtCore.QObject):
    log = ".battle.log"

    def __init__(self, args):
        super().__init__()
        times = 1
        tg = False
        # argument parsing
        for i, arg in enumerate(args):
            if arg == "--log-file":
                ConsoleApp.log = args[i + 1]
            elif arg == "--token":
                #global TOKEN
                TOKEN.append(args[i + 1])
            elif arg == "--once":
                times = 1
            elif arg == "--times":
                times = int(args[i + 1])
            elif arg == "--forever":
                times = -1
            elif arg == "--no-log":
                ConsoleApp.log = None
            elif arg == "--telegram":
                tg = True
        self._init_log()
        logger.info("== STARTED ==\n\n")
        self.games = []
        for t in TOKEN:
            self.games.append(Thread(times, t, tg))
        for t in self.games:
            t.event.connect(self._connector)
            t.start()

    def _init_log(self):
        if self.log is not None:
            l = logging.FileHandler(self.log, encoding='utf-8')
            l.setFormatter(f)
            l.setLevel(logger.level)
            logger.addHandler(l)

    @staticmethod
    def _connector(data: Action):
        if data.type == "stop":
            logger.warning("Остановлено. Причина: {}".format(data.data["reason"].upper()))
            sys.exit(0)
        elif data.type == "state":
            logger.info("Состояние игры: " + data.data["data"])
        elif data.type == "ans":
            logger.info("Получен вопрос: " + data.data["data"])


if __name__ == '__main__':
    Database.init = ('CREATE TABLE questions(id INTEGER PRIMARY KEY, q TEXT UNIQUE, corr TEXT)',)
    args = sys.argv
    qapp = QtCore.QCoreApplication(sys.argv)
    app = ConsoleApp(args)
    i = qapp.exec()
    sys.exit(i)
