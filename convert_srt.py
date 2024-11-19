import re

def convert_to_srt(translated_text):
    # Split the translated text into lines
    lines = translated_text.strip().split('\n')
    
    srt_entries = []
    current_entry = []
    
    for line in lines:
        if re.match(r'\d{2}:\d{2}:\d{2}:\d{2} - \d{2}:\d{2}:\d{2}:\d{2}', line):
            if current_entry:
                srt_entries.append(current_entry)
                current_entry = []
            current_entry.append(line)
        elif line.strip():
            current_entry.append(line)
    
    if current_entry:
        srt_entries.append(current_entry)
    
    srt_output = []
    for i, entry in enumerate(srt_entries, 1):
        timecode = entry[0]
        start, end = timecode.split(' - ')
        start = start.replace(':', ',', 2)
        end = end.replace(':', ',', 2)
        
        srt_output.append(str(i))
        srt_output.append(f"{start} --> {end}")
        srt_output.extend(entry[1:])
        srt_output.append('')
    
    return '\n'.join(srt_output)

# Placeholder for the translated text
translated_text = """
00:00:03:23 - 00:00:04:22
Ok.

00:00:04:22 - 00:00:06:09
Sim.

00:00:06:09 - 00:00:09:09
Obrigado.

00:00:12:05 - 00:00:15:05
Como eu disse,
eles simplesmente nem estavam lá.

00:00:16:22 - 00:00:19:22
Eu acho que é uma ótima jogada.

00:00:20:09 - 00:00:22:14
Eu acho que você quer.

00:00:22:14 - 00:00:23:23
Me desculpe.

00:00:23:23 - 00:00:26:23
Acho que isso é uma coisa boa.

00:00:28:23 - 00:00:31:23
Ok.

00:00:35:14 - 00:00:36:21
Ok.

00:00:36:21 - 00:01:08:03
É. Ah.

00:01:17:13 - 00:01:22:01
Então você pede desculpas por me acusar.

00:01:22:13 - 00:01:23:10
O que isso significa?

00:01:23:10 - 00:01:27:17
Você acredita em mim, ou ainda não acredita
isso significa que eu acredito em você.

00:01:27:19 - 00:01:30:16
Eu escolho acreditar em você. Certo.

00:01:30:16 - 00:01:33:16
Obrigado.

00:02:01:05 - 00:02:03:01
Certo.

00:02:03:01 - 00:02:06:01
Eu não.

00:02:07:05 - 00:02:10:05
Saiba que isso é um chuveiro,

00:02:10:07 - 00:02:11:20
e tomei um analgésico.

00:02:11:20 - 00:02:13:07
Agora mesmo.

00:02:13:07 - 00:02:16:07
Só isso.

00:02:19:00 - 00:02:21:07
Mas, tente andar para passar.

00:02:21:07 - 00:02:22:20
Sério?

00:02:22:20 - 00:02:25:20
Tão confortável.

00:02:28:22 - 00:02:31:22
Assim mesmo.

00:02:38:16 - 00:02:41:09
Quem é,

00:02:41:09 - 00:02:44:09
Quem é esse cara com quem você estava falando?

00:02:44:13 - 00:02:47:21
É meu,

00:02:47:22 - 00:02:50:22
Eu fui casado com meu

00:02:51:19 - 00:02:53:14
que não tira.

00:02:53:14 - 00:02:56:00
E minha resposta.

00:02:57:02 - 00:02:58:03
Ok.

00:02:58:03 - 00:02:59:19
Sim.

00:02:59:19 - 00:03:01:08
Desculpe. Sinto muito.

00:03:01:08 - 00:03:04:08
Foi muito agitado e interrompido por

00:03:05:17 - 00:03:08:05
exércitos de outras mulheres.

00:03:08:05 - 00:03:10:22
É como minha mãe,

00:03:10:22 - 00:03:12:02
sobrinho.

00:03:12:02 - 00:03:14:06
Ela cuidava dele e outras coisas.

00:03:14:06 - 00:03:17:06
Então esta é a casa dele,
e ele é mais como meu tio,

00:03:18:02 - 00:03:21:02
e, Esse é seu tio?

00:03:21:07 - 00:03:24:04
Sim, é mais meu tio.

00:03:24:04 - 00:03:27:14
Ok,
Eu sei que ele parece mais jovem que você.

00:03:28:12 - 00:03:30:06
E não, você

00:03:30:06 - 00:03:33:06
sabe. Não.

00:03:33:13 - 00:03:37:05
Ah, como se eu te admirasse, 50 e poucos anos.

00:03:37:05 - 00:03:39:00
Mas, enfim. Então ele.

00:03:39:00 - 00:03:42:10
Minha mãe cuidou dele
quando ele era adolescente.

00:03:42:10 - 00:03:43:23
E um garotinho.

00:03:43:23 - 00:03:48:11
Ela o ajudou a se levantar,
e então o apresentou à esposa,

00:03:49:02 - 00:03:51:22
e eles começaram a contar às pessoas

00:03:51:22 - 00:03:54:12
que são.

00:03:54:12 - 00:03:55:21
Eles têm três meninos por perto.

00:03:55:21 - 00:03:58:06
Mais velhos que meus meninos.

00:03:58:06 - 00:04:01:03
Um pouco melhor para a faculdade.

00:04:07:07 - 00:04:10:07
Ok.

00:04:16:07 - 00:04:19:09
Mas, cara.

00:04:20:05 - 00:04:22:16
Tentando descobrir
quão longe estou dessa

00:04:22:16 - 00:04:25:16
família.

00:04:33:08 - 00:04:38:11
Eu, ei, você me ouviu?

00:04:39:11 - 00:04:42:11
É, eu eu.

00:04:52:10 - 00:04:56:19
Oh. Oh.

00:04:58:16 - 00:05:02:02
Então, quais são os planos?

00:05:04:05 - 00:05:05:01
Esta semana?

00:05:05:01 - 00:05:06:23
Este fim de semana?

00:05:06:23 - 00:05:08:21
Bem, esta semana

00:05:08:21 - 00:05:11:21
ou amanhã, eu te digo, você sabe,

00:05:12:00 - 00:05:16:02
talvez do psiquiatra e ecologista
na clínica,

00:05:16:06 - 00:05:19:06
eles,

00:05:19:22 - 00:05:20:10
Providence.

00:05:20:10 - 00:05:22:11
E até agora, eles

00:05:22:11 - 00:05:24:22
dizem,

00:05:24:22 - 00:05:25:19
Mas, novamente, desculpe.

00:05:25:19 - 00:05:28:19
Está fora da sua

00:05:29:06 - 00:05:29:13
paciência.

00:05:29:13 - 00:05:33:07
Tipo, longe ou não,
mas temos que nos distanciar.

00:05:36:15 - 00:05:40:04
Eu, não, eu disse que vou.

00:05:40:15 - 00:05:43:15
Eu sinto muito pelo psicólogo

00:05:43:20 - 00:05:46:12
e a clínica do amanhã

00:05:46:12 - 00:05:47:15
pela avaliação.

00:05:47:15 - 00:05:50:08
E então.

00:05:50:08 - 00:05:52:10
E então,

00:05:52:10 - 00:05:55:10
Vou ao dentista na sexta-feira

00:05:55:16 - 00:05:58:13
e depois

00:05:58:13 - 00:05:59:22
e coisas assim.

00:06:02:20 - 00:06:04:09
Oh, meu Deus.

00:06:04:09 - 00:06:06:21
O áudio ficou virtual novamente.

00:06:06:21 - 00:06:08:06
Oh meu Deus.

00:06:08:06 - 00:06:10:12
Domingo. É do meu pai.

00:06:10:12 - 00:06:13:19
Vou almoçar com meu pai
e meu tio.

00:06:14:14 - 00:06:17:14
Cara de família

00:06:18:05 - 00:06:19:14
Até agora.

00:06:19:14 - 00:06:20:12
É.

00:06:20:12 - 00:06:23:12
Então está tudo certo.

00:06:23:16 - 00:06:26:14
É o máximo que consigo lembrar agora.

00:06:26:14 - 00:06:28:15
Sabe, eu não tenho mais nada,

00:06:28:15 - 00:06:31:15
mas você não tem nada divertido planejado.

00:06:32:00 - 00:06:34:05
Não. Não,

00:06:34:05 - 00:06:37:06
Eu não tenho nada planejado.

00:06:37:07 - 00:06:38:06
Minha mãe está viva.

00:06:38:06 - 00:06:41:06
Tenho certeza
que iremos para o centro alto

ter. Oh.

00:06:43:07 - 00:06:43:17
Que é.

00:06:43:17 - 00:06:46:17
Mal posso esperar.

00:06:47:05 - 00:06:50:00
Sim, eu sei, sei

00:06:50:00 - 00:06:51:13
todas as consultas médicas

00:06:51:13 - 00:06:54:13
e nada foi planejado.

00:06:55:07 - 00:06:58:05
Tipo, tipo mesmo.

00:06:58:05 - 00:07:01:01
Sim, é o único

00:07:01:01 - 00:07:04:01
que apenas certas pessoas gostam.

00:07:04:07 - 00:07:05:00
Como eu.

00:07:05:00 - 00:07:09:14
Nenhum dos meus amigos planeja,
e ninguém sabe que estou aqui.

00:07:10:12 - 00:07:13:12
Só como minha família

00:07:13:15 - 00:07:15:21
e algumas coisas.

00:07:15:21 - 00:07:16:14
Bem. E.

00:07:18:21 - 00:07:19:09
Você não

00:07:19:09 - 00:07:22:19
mencionou nenhuma das pessoas que você adicionou.

00:07:23:00 - 00:07:25:03
Deixe-os saber
que você estava indo para o Brasil.

00:07:25:03 - 00:07:25:14
Você está fora de.

00:07:25:14 - 00:07:28:14
Não, não, não.

00:07:32:17 - 00:07:35:17
Ok.

00:07:42:13 - 00:07:45:03
Meu Deus.

00:07:45:03 - 00:07:48:03
Bem, parece que você está levando a viagem

00:07:48:03 - 00:07:51:03
muito a sério então. Então.

00:07:52:06 - 00:07:53:23
Ok,

00:07:53:23 - 00:07:56:23
Rory.

00:07:59:05 - 00:08:02:05
Quero dizer, é isso.

00:08:03:06 - 00:08:04:22
Parece que você está levando a viagem
a sério.

00:08:04:22 - 00:08:06:19
Então isso é bom.

00:08:06:19 - 00:08:09:19
Como vai?

00:08:10:15 - 00:08:11:16
Obrigada.

00:08:11:16 - 00:08:13:12
Estou,

00:08:13:12 - 00:08:15:08
e levando o cuidado a sério.

00:08:15:08 - 00:08:18:08
Estou falando sério.

00:08:24:14 - 00:08:28:11
Quero acreditar na sua seriedade.

00:08:36:03 - 00:08:39:03
Não apenas venha.

00:08:42:16 - 00:08:43:04
Seus filhos.

00:08:43:04 - 00:08:45:22
Alguma coisa.

00:08:45:22 - 00:08:48:05
Então, você é o caminho a seguir agora.

00:08:48:05 - 00:08:50:19
Não há nada para postar.
E eu vou dizer de novo.

00:08:50:19 - 00:08:53:17
E você está escolhendo acreditar em mim.

00:08:53:17 - 00:08:56:09
Estou escolhendo acreditar.

00:08:56:09 - 00:08:59:10
Então é como se eu meio que chegasse ao lugar
onde é como.

00:09:01:03 - 00:09:03:01
É como se a única opção
fosse escolher acreditar em você.

00:09:03:01 - 00:09:04:05
A outra opção é como,

00:09:05:09 - 00:09:06:06
não, eu realmente não acredito

00:09:06:06 - 00:09:09:06
em você, mas falar com você sobre
isso não vai levar a lugar nenhum.

00:09:09:06 - 00:09:12:06
Então eu simplesmente não digo isso.

00:09:14:22 - 00:09:17:23
Você acha que dizer que não acredita em mim
é como eu dizer

00:09:17:23 - 00:09:20:23
dizer que
Eu não acredito que você vai.

00:09:21:23 - 00:09:24:23
Eu sei disso, eu sei disso, mas eu sou Jake.

00:09:25:00 - 00:09:28:05
Oh hey hey hey
hey, não precisa ser agressivo.

00:09:28:05 - 00:09:30:01
Como se eu estivesse sendo agressivo.

00:09:30:01 - 00:09:32:05
Estou literalmente apenas falando.

00:09:32:05 - 00:09:36:03
Então agora eu sinto como,
você sabe o que eu estava dizendo?

00:09:38:05 - 00:09:39:12
Lembre-se, estou horrorizado

00:09:39:12 - 00:09:42:12
agora, então estou falando de um espaço aberto.

00:09:42:12 - 00:09:45:17
É meio difícil entender
toda a sua dinâmica.

00:09:45:17 - 00:09:47:20
Você não vai.

00:09:47:20 - 00:09:52:00
Mas se você acha que eu vou
para, você sabe, me avise e eu vou.

00:09:53:02 - 00:09:55:23
Vou falar baixo.

00:09:55:23 - 00:09:57:14
Mas, não, não estou dizendo isso.

00:09:57:14 - 00:10:00:05
Não estou escolhendo agradar você agora.

00:10:00:05 - 00:10:01:21
Estou escolhendo ir embora.

00:10:01:21 - 00:10:05:18
Quando você diz que não é, sabe,

00:10:06:13 - 00:10:10:17
você não vai passar por isso, tipo,
isso simplesmente não vai ser,

00:10:11:07 - 00:10:16:04
sabe, ir a esses diferentes clubes
e festas e coisas assim.

00:10:16:04 - 00:10:18:02
Você não vai fazer essas coisas.

00:10:18:02 - 00:10:20:18
E você está lá para se concentrar em si mesmo

00:10:20:18 - 00:10:23:18
e na sua saúde mental e cura.

00:10:24:03 - 00:10:27:12
E eu acho que isso é,

00:10:29:09 - 00:10:31:13
é,

00:10:31:13 - 00:10:34:05
é uma, é uma,

00:10:34:05 - 00:10:37:12
é uma, é uma muito, virtuosa

00:10:38:09 - 00:10:41:09
busca de vida, o que é ótimo.

00:10:41:14 - 00:10:44:14
E a outra coisa é, é, é

00:10:45:10 - 00:10:48:02
seria difícil para qualquer um.

00:10:48:02 - 00:10:50:10
E também é um sacrifício.

00:10:50:10 - 00:10:52:19
Então, considerando que você faria

00:10:53:21 - 00:10:56:12
considerando que você faria isso,

00:10:56:12 - 00:10:59:15
abster-se de sair e,

00:10:59:23 - 00:11:04:23
você sabe, dançar com,
você sabe, um bando de,

00:11:05:01 - 00:11:08:17
você sabe, pessoas do Brasil ou algo
assim, todos esses diferentes

00:11:09:21 - 00:11:14:13
Eu amo que você pode colocar o, e, e,

00:11:15:16 - 00:11:18:08
o outro,

00:11:18:08 - 00:11:19:19
kizomba é

00:11:19:19 - 00:11:22:19
tão popular
lá, é como se todo mundo fizesse.

00:11:23:05 - 00:11:26:18
Então é como se eu olhasse para esse tipo de coisa,

00:11:26:18 - 00:11:29:19
e eu apenas vejo o quão sensual e sexual
um

nd e coisas assim.

00:11:29:19 - 00:11:32:02
Isso me deixaria muito desconfortável.

00:11:32:02 - 00:11:34:21
Mas, você não está.

00:11:34:21 - 00:11:36:20
Você não está fazendo isso. Eles estão. Isso.

00:11:36:20 - 00:11:39:08
Não, eu

00:11:39:08 - 00:11:42:08
então, E você está e você está,

00:11:42:11 - 00:11:45:14
você vai,
você sabe, realmente ter seios.

00:11:46:03 - 00:11:48:16
Você não tem nada para administrar.

00:11:48:16 - 00:11:51:02
Você tem filhos. O casamento,

00:11:51:02 - 00:11:54:02
você sabe, você não está tentando acompanhar
as agendas sociais.

00:11:54:06 - 00:11:55:11
Você literalmente apenas

00:11:55:11 - 00:11:59:07
mantém um ambiente para você
onde isso só machuca você e seu cérebro.

00:12:00:08 - 00:12:03:08
Como eu diria, tipo, quero dizer,

00:12:03:11 - 00:12:06:11
você sabe, as mídias sociais, tipo

00:12:07:18 - 00:12:11:05
Eu estava pensando,
tipo, eu ia dar um tempo.

00:12:11:05 - 00:12:13:14
E eles honestamente,

00:12:13:14 - 00:12:16:14
isso foi eu acho, eu acho,
eu acho que enquanto você está lá,

00:12:17:19 - 00:12:20:08
tipo, se vamos ficar por aqui

00:12:20:08 - 00:12:23:08
ficando longe das redes sociais,

00:12:24:23 - 00:12:27:17
sim, você pode, você pode temporariamente.

00:12:27:17 - 00:12:29:22
Você pode temporariamente,

00:12:29:22 - 00:12:32:02
tipo ajuda desligada,

00:12:32:02 - 00:12:34:18
tipo dar um tempo
e você não vai aparecer como você.

00:12:34:18 - 00:12:37:00
Você não vai aparecer em lugar nenhum.
Você não vai aparecer no messenger.

00:12:37:00 - 00:12:41:11
Você sabe, você não vai aparecer
no Instagram ou qualquer coisa.

00:12:41:11 - 00:12:43:02
Tipo, você pode dar uma pausa
em cada um individualmente

00:12:43:02 - 00:12:46:11
e isso não apaga nada,
sabe, só reinicia mais tarde.

00:12:47:17 - 00:12:49:12
Mas então,

00:12:49:12 - 00:12:52:12
Quero dizer, as pessoas não seriam capazes
de entrar em contato com você nas redes sociais,

00:12:52:17 - 00:12:54:04
mas você não está preocupado com elas.

00:12:54:04 - 00:12:56:03
Então não, não.

00:12:58:21 - 00:13:01:03
Sabe, eu tive uma ideia.

00:13:01:03 - 00:13:04:03
Eu estava pensando no.

00:13:05:12 - 00:13:07:09
Eu vou

00:13:07:09 - 00:13:11:01
fazer, você sabe, um diário em vídeo para mim

00:13:12:14 - 00:13:15:14
uma vez por dia.

00:13:16:09 - 00:13:17:21
Isso seria.

00:13:17:21 - 00:13:20:08
Isso seria.

00:13:20:08 - 00:13:22:22
Isso seria difícil.

00:13:22:22 - 00:13:24:19
E,

00:13:24:19 - 00:13:27:10
Estou pensando que não vou fazer isso.

00:13:27:10 - 00:13:28:05
Sério.

00:13:28:05 - 00:13:31:05
Quando você me ligou mais cedo
e eu estava do lado de fora da rede,

00:13:31:07 - 00:13:36:09
Eu tinha acabado de começar, tipo, a fazer um vídeo
dizendo o que eu estava, como me sentindo.

00:13:36:22 - 00:13:39:20
Então você tem,

00:13:39:20 - 00:13:42:00
Sabe, eu era engraçado.

00:13:42:00 - 00:13:44:16
Eu só queria, tipo.

00:13:44:16 - 00:13:47:16
Eu só quero ser intencional.

00:13:51:15 - 00:13:52:17
Por, tipo, agora mesmo.

00:13:52:17 - 00:13:55:06
Aqui, tem isso.

00:13:55:06 - 00:13:58:06
Então o que eu faço na vida dele?

00:13:58:08 - 00:14:00:09
E então meu outro.

00:14:00:09 - 00:14:02:20
Você ouve as músicas como.

00:14:02:20 - 00:14:05:09
Desculpe, estou falando muito baixo.

00:14:05:09 - 00:14:07:00
Desculpe.

00:14:07:00 - 00:14:08:06
O silêncio não é o problema.

00:14:08:06 - 00:14:12:05
É como a proximidade da sua boca
para, estrangeiros mantém,

00:14:12:05 - 00:14:15:08
tipo, muda para frente e para trás,
e fica, tipo, muito, muito lento.

00:14:15:08 - 00:14:16:10
Mas eu não estou.

00:14:16:10 - 00:14:18:19
Está, tipo, na
cama, e eu estou deitado na cama.

00:14:21:11 - 00:14:24:11
Provavelmente, apenas um militar,

00:14:24:14 - 00:14:27:12
talvez sua cabeça em casa ou algo assim,
não sei.

00:14:27:12 - 00:14:28:09
Sim.

00:14:28:09 - 00:14:32:13
Sempre algo com seu telefone
por algum motivo, tipo, você sabe, tipo,

00:14:32:22 - 00:14:35:22
abafado quando tento ouvir você.

00:14:37:18 - 00:14:38:02
Ok.

00:14:38:02 - 00:14:41:02
Deixe-me ver se consigo fazer isso acontecer.

00:14:44:02 - 00:14:45:15
Você me ouviu? Agora?

00:14:45:15 - 00:14:47:11
Sim.

00:14:47:11 - 00:14:49:01
Melhor.

00:14:49:01 - 00:14:52:01
Sim, eu consigo ouvir.

00:14:54:20 - 00:14:55:07
Sim.

00:14:55:07 - 00:14:58:07
E então eu sou como um vídeo.

00:14:58:11 - 00:15:01:11
Como hoje.

00:15:01:23 - 00:15:04:23
Talvez te mostrar algo,

00:15:05:07 - 00:15:09:01
e estou falando comigo mesmo.

00:15:10:12 - 00:15:13:12
Tentando tentar a coisa que você.

00:15:15:05 - 00:15:18:02
Sabe, você sugeriu ou,

00:15:18:02 - 00:15:21:16
Quer dizer, eu não faço os vídeos, eu só,

00:15:21:16 - 00:15:24:16
Eu, eu gosto muito de me gravar,
falar comigo mesmo.

00:15:25:17 - 00:15:28:17
Sempre que o vídeo

00:15:29:02 - 00:15:29:20
até agora.

00:15:29:20 - 00:15:34:03
Então eu ia começar, pensar como,
também como algumas das coisas, como,

00:15:34:03 - 00:15:38:22
Eu quero enviar algo positivo, sabe,
vou enviar para os meninos pensarem.

00:15:39:00 - 00:15:40:17
Certo. Então, mas estamos sentados

g bem ali,

00:15:42:14 - 00:15:43:04
Eu também estou tipo,

00:15:43:04 - 00:15:47:00
falando e, e eu,
Eu também quero falar e tipo,

00:15:47:18 - 00:15:50:23
mostrar aos garotos o senso dos garotos,
você sabe, pensar, oh,

00:15:52:19 - 00:15:55:19
sim.

00:16:00:18 - 00:16:03:18
Corajoso
vulnerabilidade é muito inspirador.

00:16:09:12 - 00:16:12:12
Até para nós mesmos.

00:16:17:19 - 00:16:20:19
É. Tipo

00:16:21:22 - 00:16:22:20
pode ser um problema.

00:16:22:20 - 00:16:25:20
Cheguei a um ponto em que
me encontrei

00:16:26:16 - 00:16:29:16
pedindo desculpas por tudo.

00:16:29:20 - 00:16:32:08
Tipo, eu só preciso de um idiota,

00:16:32:08 - 00:16:36:21
pedir desculpas caso eu, tipo, chateie alguém.

00:16:40:07 - 00:16:42:22
Bem, porque você está me tocando, eu acho.

00:16:42:22 - 00:16:45:11
Não, não,
Estou falando de, tipo, pessoas como você.

00:16:45:11 - 00:16:48:22
Pessoa falando pessoalmente, tipo,
Eu, eu, eu, tipo,

00:16:49:06 - 00:16:52:21
dizer algo, e então eu gostaria,
sabe, sentir como, bem,

00:16:52:21 - 00:16:54:13
talvez não fosse a coisa certa
a dizer ou algo assim.

00:16:54:13 - 00:16:56:20
E tipo, eu pediria desculpas ou,

00:16:56:20 - 00:17:00:14
sabe, algo que tanto faz,
tipo eu só pediria desculpas, tipo,

00:17:00:14 - 00:17:05:01
por incessantemente
depois que você termina assim.

00:17:05:01 - 00:17:07:12
Eu estava meio que fazendo isso

00:17:08:16 - 00:17:09:22
demais.

00:17:09:22 - 00:17:14:01
E eu encontrei palavras diferentes para dizer,
mas eu meio que fiz isso de propósito

00:17:14:13 - 00:17:18:19
porque eu estava tipo, eu queria que todos
ao meu redor soubessem que eu não estava.

00:17:18:19 - 00:17:21:19
Eu não tinha problema em cometer erros.

00:17:22:10 - 00:17:25:10
Foi um grande negócio
com essa declaração. Você

00:17:26:09 - 00:17:30:06
você escreveu como se estivesse tentando esconder os,
os, os erros deles e coisas assim.

00:17:30:11 - 00:17:32:06
Merda,

00:17:32:06 - 00:17:35:01
você destruiu pra caralho.

00:17:35:01 - 00:17:37:23
Então você tinha que ser tipo,

00:17:37:23 - 00:17:40:03
estúpido, vulnerável e transparente.

00:17:40:03 - 00:17:43:03
Você sabe, quando ficou emocional.

00:17:44:08 - 00:17:47:08
É.

00:17:47:16 - 00:17:50:21
Muito bom ter isso.

00:17:51:03 - 00:17:54:01
Certamente tornou mais fácil

00:17:54:01 - 00:17:56:18
cometer erros e sinceramente se sentir mal

00:17:56:18 - 00:17:59:18
por cometê-los.

00:18:02:20 - 00:18:05:19
Sim.

00:18:07:05 - 00:18:10:04
Bem, esse é o objetivo.

00:18:12:19 - 00:18:15:12
Do que eles dizem.

00:18:15:12 - 00:18:18:12
Sabe, eu sinto como.

00:18:19:04 - 00:18:21:08
Eu estava

00:18:21:08 - 00:18:24:18
Eu lembro de um momento na minha vida
que eu lembro do ano em que nós

00:18:25:18 - 00:18:26:11
então.

00:18:26:11 - 00:18:29:12
E então, novamente, eu acho que é
quando você começa a falar tipo,

00:18:29:12 - 00:18:32:18
baixinho, você meio que resmunga um pouco
isso é difícil de ouvir, sabe?

00:18:32:19 - 00:18:33:19
Sim.

00:18:33:19 - 00:18:36:18
Estou resmungando cansado, certo.

00:18:37:08 - 00:18:41:21
Sim.

00:18:46:11 - 00:18:46:15
Desculpe.

00:18:46:15 - 00:18:49:01
Eu não sei de nada

00:18:49:01 - 00:18:52:01
chocante sobre seu número.

00:18:52:07 - 00:18:55:06
Tipo, há muito tempo
você estava dizendo que as pessoas,

00:18:55:06 - 00:18:58:05
Eu acho que as pessoas, você apenas,

00:18:59:07 - 00:19:01:23
você sabe, ser capaz de fazer isso e ir.

00:19:01:23 - 00:19:04:02
Mas havia pessoas fazendo isso.

00:19:04:02 - 00:19:07:02
Eu lembro de praticar,

00:19:08:10 - 00:19:10:19
ou ser melhor nisso.

00:19:10:19 - 00:19:15:04
E eu acho que em algum momento,
isso definitivamente

00:19:16:08 - 00:19:18:00
definitivamente não é algo que você gosta.

00:19:18:00 - 00:19:21:00
Você é e você faz com isso. Não é como,

00:19:21:15 - 00:19:22:10
o que você disse?

00:19:22:10 - 00:19:23:21
Você só está dizendo, tipo,

00:19:23:21 - 00:19:26:21
sua voz simplesmente some às vezes
no final das frases e é difícil.

00:19:26:23 - 00:19:28:16
Sim. Legal.

00:19:28:16 - 00:19:31:15
Eu, eu sinto muito, tipo eu, eu faço isso.

00:19:31:17 - 00:19:32:19
Eu gosto

00:19:34:07 - 00:19:34:15
Sim.

00:19:34:15 - 00:19:38:05
Não, eu, eu não sei, eu só,
eu estava falando como você disse ainda,

00:19:38:11 - 00:19:41:11
Eu era um tipo.

00:19:42:18 - 00:19:45:18
Sabe, a habilidade de fazer isso
e ser constante,

00:19:46:14 - 00:19:49:14
como todo mundo, eu acho,

00:19:50:06 - 00:19:52:21
faz com que

00:19:52:21 - 00:19:55:18
lembrete consciente

00:19:55:18 - 00:19:57:01
e. Sim.

00:19:57:01 - 00:19:58:20
Ok.

00:19:58:20 - 00:20:01:04
Definitivamente libertador para mim.

00:20:01:04 - 00:20:03:02
Eu lembro disso para você.

00:20:03:02 - 00:20:04:23
Isso significa o quê?

00:20:04:23 - 00:20:09:05
Bem, você sabe, pode ser tóxico para
para onde você está se desculpando demais,

00:20:09:05 - 00:20:10:12
e então você simplesmente tem esse tipo

00:20:10:12 - 00:20:14:11
de apenas um sentimento geral
de responsabilidade e coisas assim.

00:20:14:11 - 00:20:16:03
E esse não é um bom lugar para se estar.

0:20:16:03 - 00:20:19:03
Mas, você sabe, definitivamente

00:20:19:19 - 00:20:22:19
sabe que você chega ao ponto
onde você faz isso,

00:20:24:02 - 00:20:26:00
como se isso fosse

00:20:26:00 - 00:20:29:00
ser capaz de fazer
essa é a única maneira de você se amar.

00:20:29:12 - 00:20:31:16
Honestamente,

00:20:31:16 - 00:20:35:02
ser capaz de lidar com isso, a única maneira
de você se amar porque você não consegue.

00:20:35:02 - 00:20:35:11
Porque

00:20:35:11 - 00:20:38:23
porque ninguém se orgulha do seu comportamento
quando fazem merdas como essa.

00:20:39:15 - 00:20:43:20
Quando você entra nisso se punindo
ou não porque cometeu um erro,

00:20:44:11 - 00:20:48:17
bem, o que você bem sabe, você segue com isso,
você segue com uma justificativa

00:20:48:17 - 00:20:51:04
ou você segue com uma falácia
e a armazena.

00:20:51:04 - 00:20:54:17
Mas no fundo, você sabe, foi uma merda
e não vai a lugar nenhum.

00:20:55:03 - 00:20:58:03
E você,
isso significa que você não consegue olhar para si mesmo.

00:20:58:05 - 00:21:00:23
Você não consegue descobrir como dar a si mesmo
graça.

00:21:00:23 - 00:21:03:23
Você não consegue olhar para si mesmo
e se aceitar.

00:21:04:07 - 00:21:09:20
Aceite-se de verdade
e não em um sentido onde, tipo

00:21:09:20 - 00:21:12:20
Eu aceito que você, você sabe,

00:21:13:09 - 00:21:16:22
machuque as pessoas,
você sabe, de propósito ou algo assim.

00:21:16:22 - 00:21:18:01
E não peça desculpas por isso.

00:21:18:01 - 00:21:21:01
Agora assim,
essa conversa não é foda.

00:21:21:07 - 00:21:21:14
Certo?

00:21:21:14 - 00:21:27:21
Então você não pode se dar
graça e amar a si mesmo.

00:21:29:20 - 00:21:31:22
Todas as partes disso,

00:21:31:22 - 00:21:34:09
e entender a si mesmo nesses momentos.

00:21:34:09 - 00:21:37:10
Não há como amar a si mesmo
a menos que você possa se desculpar menos.

00:21:37:10 - 00:21:38:15
Você pode seguir seus erros.

00:21:38:15 - 00:21:41:15
Você pode realmente agir assim

00:21:41:19 - 00:21:43:05
porque é só carma.

00:21:43:05 - 00:21:46:04
Simplesmente começa em cima de você
e você nunca sai de baixo dele.

00:21:46:04 - 00:21:49:04
As pessoas continuam cometendo os mesmos
erros de merda repetidamente.

00:21:52:21 - 00:21:55:21
É isso.

00:21:56:22 - 00:21:57:10
Cedo.

00:21:57:10 - 00:22:00:06
É um pé na cova cedo

00:22:00:06 - 00:22:03:08
também, porque é muito estressante
e muito valorizado sistema nervoso.

00:22:03:08 - 00:22:07:05
E nosso. Cara.

00:22:17:21 - 00:22:18:08
É uma droga.

00:22:18:08 - 00:22:21:08
É como. É como se eu estivesse fumando um cigarro.

00:22:21:20 - 00:22:24:00
Entra no carro.

00:22:24:00 - 00:22:27:07
E é difícil parar,
então não vou fazer isso.

00:22:33:07 - 00:22:33:18
Você está dizendo

00:22:33:18 - 00:22:36:18
que finalmente vai parar de fumar?

00:22:38:09 - 00:22:40:10
Foi isso
que você entendeu do que eu acabei de dizer.

00:22:40:10 - 00:22:40:22
Você sabe,

00:22:41:21 - 00:22:44:10
simplesmente gostava do meu trabalho.

00:22:44:10 - 00:22:45:14
Aquilo ali?

00:22:45:14 - 00:22:48:10
Sim. Tenho pensado sobre isso.

00:22:48:10 - 00:22:56:01
Estou em ótima forma agora.

00:22:56:01 - 00:22:59:03
Vou perder mais 5 libras, então.

00:23:01:05 - 00:23:04:05
Eu adoraria.

00:23:04:06 - 00:23:06:11
Ter meus pulmões limpos também.

00:23:06:11 - 00:23:09:11
Eu provavelmente faria isso.

00:23:13:11 - 00:23:16:09
Gravando o vídeo hoje,

00:23:16:09 - 00:23:18:12
Eu posso realmente sentar
na frente da câmera com as luzes

00:23:18:12 - 00:23:22:20
e a ideia do que eu queria dizer
e tudo, então.

00:23:24:13 - 00:23:27:13
E eu entrei no escritório,

00:23:28:11 - 00:23:30:23
no escritório.

00:23:30:23 - 00:23:33:06
No escritório. Sim.

00:23:33:06 - 00:23:38:04
Sim, eu tinha meu microfone ligado e tudo mais, então.

00:23:38:22 - 00:23:41:21
Ah, o.

00:23:44:12 - 00:23:47:18
Eu quero, preciso substituir a TV
e então a TV 4k ali.

00:23:47:18 - 00:23:52:23
Assim eu posso, mas como eu disse,
que porra de TV 4K de verdade. Mas

00:23:55:08 - 00:23:55:16
Eu preciso

00:23:55:16 - 00:23:58:16
para conseguir, eu preciso, eu preciso que isso desacelere,

00:23:58:16 - 00:24:01:15
e eu preciso ler o roteiro,

00:24:01:18 - 00:24:04:18
e eu preciso, tipo,
entender o fluxo geral disso,

00:24:05:10 - 00:24:08:10
você sabe, dedicar um pouco de memória
e fazer isso,

00:24:08:16 - 00:24:10:00
você sabe, ter feito os marcos

00:24:10:00 - 00:24:13:02
nos pontos meio que fazem sentido relação
em relação um ao outro.

00:24:13:02 - 00:24:16:10
Então é mais fácil para mim lembrar
o que estou dizendo. Mas,

00:24:17:21 - 00:24:19:11
você sabe, como a presença de Jordan Jordan

00:24:19:11 - 00:24:22:16
na câmera porque eu estava
eu bati nele pra caramba

00:24:22:21 - 00:24:25:21
quando você veio pela primeira vez
porque ele estava em todo lugar.

00:24:26:10 - 00:24:30:01
Mas eu lembro disso agora que eu posso
agora que eu entrei, tipo,

00:24:30:04 - 00:24:35:01
merda tipo para a câmera, eu não posso checar
porque em isolamento é bom.

00:24:35:10 - 00:24:38:05
Sua presença é boa.

00:24:40:13 - 00:24:4
1:23
É só repetição.

00:24:41:23 - 00:24:43:17
Eu sei exatamente como é.

00:24:43:17 - 00:24:45:20
Eu sei que parece apenas.

00:24:45:20 - 00:24:48:11
Eu não tenho a realidade, sabe?

00:24:48:11 - 00:24:51:18
Malditos olhos mortos na câmera,
sabe?

00:24:52:11 - 00:24:55:15
E então, e então, você sabe,

00:24:55:15 - 00:24:59:00
não acreditar naquela energia
e não acreditar naquele contato visual.

00:24:59:19 - 00:25:02:19
Tipo, isso é muito difícil de fazer.

00:25:03:01 - 00:25:04:08
E ser

00:25:04:08 - 00:25:07:22
e entregar uma fala,
honestamente onde os sentimentos

00:25:07:23 - 00:25:12:23
e a emoção realmente aparece
porra como se ele tivesse dificuldade em fazer isso.

00:25:12:23 - 00:25:15:23
Assim como a emoção.

00:25:16:20 - 00:25:19:08
Mas ele é muito bom em

00:25:19:08 - 00:25:22:08
ele também divaga como porra meu,

00:25:23:18 - 00:25:26:18
mas mas esse é

00:25:27:16 - 00:25:29:15
o ponto

00:25:29:15 - 00:25:32:14
e como dizemos os pontos agora,

00:25:32:15 - 00:25:34:21
você sabe, há uma psicologia nisso.

00:25:34:21 - 00:25:37:00
E então ele é como contato visual.

00:25:37:00 - 00:25:40:00
Só que neste caso é perfeito.

00:25:40:15 - 00:25:41:11
É muito, muito bom.

00:25:45:23 - 00:25:48:07
Então é aí que eu quero chegar.

00:25:48:07 - 00:25:52:16
Então eu preciso, eu,
você juntar um monte de scripts.

00:25:54:03 - 00:25:57:03
Só escreva mais um pouco.

00:25:58:18 - 00:26:01:18
Comece a praticar.

00:26:04:06 - 00:26:06:08
Sim, eu me amo.

00:26:06:08 - 00:26:09:08
Provavelmente a parte fácil para você.

00:26:09:10 - 00:26:11:10
Eu não ouvi o que você acabou de dizer.

00:26:11:10 - 00:26:14:10
Eu disse que essa seria a parte fácil
para você

00:26:14:21 - 00:26:17:21
e não,

00:26:19:11 - 00:26:20:20
Eu vou superar isso.

00:26:20:20 - 00:26:22:05
Não sei se vai ser fácil.

00:26:22:05 - 00:26:25:05
Definitivamente, tipo.

00:26:26:11 - 00:26:30:04
É diferente quando estou me gravando,
então talvez não seja um problema tão grande.

00:26:30:04 - 00:26:33:04
Não será um problema tão grande. Mas,

00:26:33:08 - 00:26:37:06
sabe,
geralmente sou autoconsciente sobre

00:26:37:10 - 00:26:40:16
quantas palavras
eu costumava falar e descrever as coisas.

00:26:41:18 - 00:26:46:10
Porque eu sei que eu corro e eu você

00:26:48:02 - 00:26:50:10
vagar no divagar.

00:26:50:10 - 00:26:51:13
E eu não estou.

00:26:51:13 - 00:26:55:04
Eu realmente não acho que estou divagando,
como se eu estivesse realmente trabalhando assim.

00:26:55:04 - 00:26:57:09
E eu estou tipo, bem, sim,
eu sei que estou trabalhando,

00:26:57:09 - 00:27:00:09
como através de todo o universo disso
e explicando como tudo.

00:27:01:08 - 00:27:03:01
Sim, é verdade, é verdade.

00:27:03:01 - 00:27:06:19
Eu digo tipo, sim, eu sinto que às vezes
você vai divagar, mas você realmente

00:27:07:16 - 00:27:10:16
fazendo um ponto e trazendo de volta.

00:27:10:22 - 00:27:11:11
Sim.

00:27:11:11 - 00:27:15:22
Bem, o problema é que eu posso não
Eu posso não trazer de volta em tempo hábil

00:27:15:22 - 00:27:20:03
modo ou de jeito nenhum porque eu, você sabe,
esqueço o que eu estava dizendo ou algo assim.

00:27:20:10 - 00:27:22:13
Eu melhorei muito nisso, no entanto.

00:27:22:13 - 00:27:24:16
Sim.

00:27:24:16 - 00:27:27:09
E isso realmente acontece
por causa da disciplina que eu tinha

00:27:27:09 - 00:27:28:21
quando eu estava fazendo os vídeos.

00:27:28:21 - 00:27:31:00
Havia algo que era importante
vídeo

00:27:31:00 - 00:27:34:09
e eu começava a fazer isso e eu
esquecia de voltar ao ponto.

00:27:34:09 - 00:27:36:04
E eles eram
muito longos, e eu conseguia andar.

00:27:37:07 - 00:27:39:17
Então meus vídeos

00:27:39:17 - 00:27:42:21
desde então, meus vídeos
melhoraram muito.

00:27:43:22 - 00:27:46:19
Então sim, eu estava praticando.

00:27:46:19 - 00:27:50:15
Além disso, minha enunciação, como eu
há certas sílabas

00:27:50:15 - 00:27:53:15
e coisas assim
que eu digo que são muito esmagadas

00:27:53:20 - 00:27:56:20
e não parece

00:27:57:06 - 00:27:59:12
muito claramente.

00:27:59:12 - 00:28:02:12
É um pouco, é meio que.

00:28:05:22 - 00:28:08:22
Algo assim.

00:28:11:22 - 00:28:14:22
Estou perdendo.

00:28:17:07 - 00:28:18:21
Então, de novo, é isso.

00:28:18:21 - 00:28:21:07
Eu te perdi por um segundo.

00:28:21:07 - 00:28:22:09
Ah, eu só estava dizendo.

00:28:22:09 - 00:28:25:14
Eu só estava dizendo isso,

00:28:28:05 - 00:28:28:12
Porra.

00:28:28:12 - 00:28:29:11
Eu esqueci o que eu estava dizendo.

00:28:29:11 - 00:28:34:00
Eu estava, acho que estava apenas dizendo, dizendo
que eu só preciso ter alguma repetição

00:28:34:00 - 00:28:35:13
estar na frente da câmera porque eu,

00:28:35:13 - 00:28:38:08
Eu tenho um pouco
de autoconsciência sobre continuar,

00:28:38:08 - 00:28:41:17
e meus vídeos ficaram muito melhores desde que eu,
tipo, me forcei a, tipo,

00:28:41:17 - 00:28:44:03
lembrar do que eu estava falando
e voltar ao ponto.

00:28:45:16 - 00:28:46:22
E isso ajudou muito.

00:28:46:22 - 00:28:50:13
Mas há um monte de coisas
como, como eu disse, a nota esmagada

00:28:51:01 - 00:28:53:17
não notas, mas há como

00:28:53:17 - 00:28:56:17
há algumas sílabas
que eu digo onde eu simplesmente tenho muito.

00:28:57:05 - 00:28:59:05
Eu não sei
se não é necessariamente balançando,

00:28:59:05 - 00:29:03:00
mas é apenas como uma vocalização preguiçosa
da, da, da sílaba.

00:29:03:19 - 00:29:06:09
E então, soa, é

00:29:06:09 - 00:29:09:09
muito perturbador, como se eu me ouvisse
e eu pensasse, por que diabos você fez isso?

00:29:09:20 - 00:29:13:00
Então eu tenho que tentar descobrir
o que são,

00:29:13:09 - 00:29:16:09
e eu tenho que começar a praticar
limpar meu

00:29:17:04 - 00:29:19:13
meu discurso porque é

00:29:19:13 - 00:29:22:23
muito,

00:29:22:23 - 00:29:25:23
se eu estou tentando dizer algo
que é estruturado,

00:29:26:00 - 00:29:28:15
vai ser realmente uma distração
quando eu estiver sentado na varanda

00:29:28:15 - 00:29:31:03
e eu estou apenas andando de um lado para o outro
e para o outro e apenas,

00:29:31:03 - 00:29:33:10
você sabe, balbuciando para minha câmera

00:29:33:10 - 00:29:36:00
como se isso realmente funcionasse para mim
porque é parte da minha personalidade.

00:29:36:00 - 00:29:38:22
Mas, você sabe,
sendo como uma alta produção,

00:29:38:22 - 00:29:42:13
como um bom vídeo com, tipo,
boa iluminação e todas essas outras coisas

00:29:42:13 - 00:29:43:14
como se isso não pudesse estar lá.

00:29:45:12 - 00:29:47:04
E sim,

00:29:47:04 - 00:29:49:12
tira isso,
tira do filme.

00:29:49:12 - 00:29:52:12
A qualidade da produção.

00:29:53:18 - 00:29:56:00
Então eu preciso

00:29:56:00 - 00:29:58:23
aprender a falar, porra.

00:30:00:13 - 00:30:03:13
Enquanto eu realmente ouço.

00:30:03:22 - 00:30:05:17
E então você

00:30:05:17 - 00:30:07:23
como se estivesse dizendo
você precisa aprender a falar.

00:30:07:23 - 00:30:10:22
E eu sinto que,

00:30:12:00 - 00:30:12:19
sinto que não vejo

00:30:12:19 - 00:30:15:19
qualquer, tipo, bem o suficiente mais

00:30:15:20 - 00:30:16:12
o que você está acostumado.

00:30:16:12 - 00:30:19:22
Então descendo a colina,
meu inglês nunca foi feito até o topo.

00:30:19:22 - 00:30:24:10
Então eu não estava tendo que fazer,
tipo, um policial para alguma coisa.

00:30:24:10 - 00:30:26:06
E é simplesmente doloroso.

00:30:26:06 - 00:30:27:16
É como legitimamente. Por quê?

00:30:27:16 - 00:30:31:19
Como se fosse doloroso ouvir isso.

00:30:31:19 - 00:30:33:16
Eu nunca realmente faço.

00:30:33:16 - 00:30:36:16
Ou o problema.

00:30:37:05 - 00:30:38:18
Ah, você vai ficar lá por seis semanas.

00:30:38:18 - 00:30:41:14
Você tem bastante prática.

00:30:41:14 - 00:30:44:13
Ah, sim.

00:30:44:13 - 00:30:46:12
Certo. Ótimo

00:30:46:12 - 00:30:48:05
prática. Duas maneiras de fazer isso.

00:30:48:05 - 00:30:49:04
Você tem que encarar isso.

00:30:51:02 - 00:30:51:18
Mais ou menos o que você faz

00:30:51:18 - 00:30:54:18
quando você vai para aquele lugar por seis semanas.

00:30:55:13 - 00:30:56:02
Sim.

00:30:56:02 - 00:30:59:04
Nas minhas seis semanas.

00:31:01:17 - 00:31:04:09
Não, não, não, não. Sabe

00:31:04:09 - 00:31:07:09
quem os estruturou?

00:31:09:16 - 00:31:14:11
É esse que deveria me mandar uma mensagem.

00:31:14:11 - 00:31:16:18
Ei, vou jantar

00:31:16:18 - 00:31:19:18
isso.

00:31:26:01 - 00:31:29:01
Parece que você tem que me fazer um mistério

00:31:30:20 - 00:31:34:18
Estou chegando agora.

00:31:36:02 - 00:31:39:14
Então eu saio de uma vaga de estacionamento e então,

00:31:41:23 - 00:31:43:14
Sim.

00:31:43:14 - 00:31:45:22
Ok. Certo.

00:31:45:22 - 00:31:47:11
Essa é uma boa questão. Participação.

00:31:47:11 - 00:31:49:19
E, sim.

00:31:49:19 - 00:31:50:18
Certo.

00:31:50:18 - 00:31:53:12
Vou jantar.

00:31:53:12 - 00:31:53:20
Não sei.

00:31:53:20 - 00:31:57:07
Minha mãe é esse cara, vamos nos divertir

00:31:57:10 - 00:32:00:10
sem falar com você.

00:32:00:10 - 00:32:03:10
Foi bom falar com você. Você.

00:32:04:21 - 00:32:05:08
Sim.

00:32:05:08 - 00:32:08:08
Uma maneira interessante de falar sobre.

00:32:09:23 - 00:32:12:14
As coisas que precisamos falar
sem falar diretamente.

00:32:12:14 - 00:32:15:05
Então isso foi muito chique.

00:32:19:04 - 00:32:19:23
Passos de bebê.

00:32:19:23 - 00:32:22:23
Voltando aos passos do bebê.

00:32:23:20 - 00:32:26:09
Selecione tudo
começando de baixo.

00:32:26:09 - 00:32:27:13
Só tentando fazer. Certo.

00:32:27:13 - 00:32:30:06
Bom momento. Então.

00:32:30:06 - 00:32:32:15
Bem, e então eu te amo. Você.

00:32:32:15 - 00:32:33:18
Oh, você. Ah, claro.

00:32:33:18 - 00:32:36:18
Um pedido de desculpas muito melhor.

00:32:39:10 - 00:32:41:05
Ela não separou nossa família.

00:32:41:05 - 00:32:42:00
O quê?

00:32:42:00 - 00:32:45:00
Vou pensar sobre isso.

00:32:46:19 - 00:32:47:19
Ok.

00:32:47:19 - 00:32:50:19
Não, não posso me desculpar.

00:32:51:09 - 00:32:53:14
Eu posso reconhecer minhas coisas sobre, tipo, eu.

00:32:53:14 - 00:32:55:20
Eu realmente não gostei.

00:32:55:20 - 00:32:58:20
Vou pedir desculpas.

2:59:07 - 00:33:00:19
Quando eu queria ser real.

00:33:00:19 - 00:33:03:11
Tipo, a um nível que, você sabe, tipo
eu preciso.

00:33:03:11 - 00:33:08:05
Eu preciso chegar ao ponto em que eu sinta
que preciso fazer isso. Eu.

00:33:10:12 - 00:33:11:20
Sim,

00:33:11:20 - 00:33:15:08
Eu acho, eu acho que ela,
eu acho que eu acho que isso foi muito legal. Dra..

00:33:15:09 - 00:33:17:07
Eu concordo com você. Então eu vou me desculpar.

00:33:22:20 - 00:33:27:18
Ah. Sim, eu sei, eu sei, você sabe,

00:33:28:23 - 00:33:31:13
o que torna difícil

00:33:31:13 - 00:33:34:22
experimentar e ignorar,

00:33:35:19 - 00:33:38:19
mas eu acho, eu acho,

00:33:38:22 - 00:33:41:22
eu acho
se isso simplesmente não continuasse acontecendo,

00:33:42:08 - 00:33:45:23
eu acho que isso tornaria tudo melhor,
porque

00:33:46:14 - 00:33:49:01
mesmo que fosse apenas um pedido de desculpas
e fosse um pedido de desculpas de meia hora,

00:33:49:01 - 00:33:52:16
desde que não aconteça de novo
e de novo, de novo, então

00:33:53:04 - 00:33:58:01
o desculpe realmente significaria algo
como um simples desculpe seria eu.

00:33:58:08 - 00:34:01:07
Você estaria falando sério quando dissesse isso.

00:34:01:07 - 00:34:04:07
Mas quando você diz desculpe, sim, faça de novo.

00:34:04:07 - 00:34:06:19
É como se isso simplesmente me destruísse.
Como se fosse um soco no estômago.

00:34:06:19 - 00:34:10:12
Como se meu advogado estivesse me explicando
como Janice me trata até agora.

00:34:10:13 - 00:34:14:10
É muito tipo, é só
isso realmente me tira o fôlego.

00:34:15:13 - 00:34:18:06
E eu não consigo acreditar.

00:34:18:06 - 00:34:21:06
E eu sou sugado para dentro disso e

00:34:21:17 - 00:34:24:17
é muito ruim.

00:34:26:17 - 00:34:27:10
É muito ruim.

00:34:27:10 - 00:34:28:01
Você tem que fazer isso.

00:34:28:01 - 00:34:31:01
Eu tenho que não fazer isso.

00:34:32:18 - 00:34:35:12
É.

00:34:35:12 - 00:34:38:12
Quero dizer.

00:34:39:00 - 00:34:39:11
Me desculpe.

00:34:39:11 - 00:34:43:16
Porque é meio que algo
então estou reconhecendo que

00:34:43:16 - 00:34:48:08
Eu tenho limites tão baixos agora que
se eu tivesse limites maiores,

00:34:48:21 - 00:34:52:14
na melhor das hipóteses, você teria
levado eles a sério e talvez parado.

00:34:53:11 - 00:34:56:05
Ou a outra opção seria
que não estaríamos juntos

00:34:56:05 - 00:34:59:04
de jeito nenhum.

00:34:59:16 - 00:35:01:12
E eu estou

00:35:01:12 - 00:35:04:17
tentando entender
por que não consigo implementar esses limites

00:35:04:17 - 00:35:07:17
com você.

00:35:10:02 - 00:35:12:10
Conhece alguns?

00:35:12:10 - 00:35:15:10
Definitivamente. Eu.

00:35:16:08 - 00:35:19:08
Algo que exploraria.

00:35:20:20 - 00:35:23:17
Realmente compreensivo.

00:35:23:17 - 00:35:27:09
E o porquê eu posso.

00:35:29:12 - 00:35:32:04
Fazer um monte de coisas

00:35:32:04 - 00:35:35:04
agora mesmo.

00:35:37:10 - 00:35:39:09
Sim.

00:35:39:09 - 00:35:42:12
Eu não sei como está minha jornada de cura,

00:35:43:09 - 00:35:47:16
minha jornada de cura é ser capaz
de, sem sombra de dúvida.

00:35:49:03 - 00:35:51:02
Tudo bem.

00:35:51:02 - 00:35:52:17
Sabe, sem

00:35:52:17 - 00:35:55:22
a sombra de dúvida que eu posso dizer
é assim que eu me sinto.

00:35:57:03 - 00:36:00:20
Que é isso que eu não quero que aconteça.

00:36:01:18 - 00:36:04:18
E eu posso realmente impor um limite
e dizer,

00:36:05:01 - 00:36:07:16
se você fizer isso de novo, então isso

00:36:07:16 - 00:36:10:20
e será como minha decisão e pronto.

00:36:11:16 - 00:36:14:16
Tipo, é nisso que estou focando na cura.

00:36:15:19 - 00:36:18:06
Eu tenho que

00:36:18:06 - 00:36:19:06
Eu acho que isso é bom.

00:36:19:06 - 00:36:22:06
E eu acho que todo mundo para isso,

00:36:22:14 - 00:36:25:08
Candace por isso para mim,

00:36:25:08 - 00:36:29:16
A Amy fez isso comigo e agora você e eu,
e eu não aguento mais.

00:36:29:16 - 00:36:33:12
E eu vi um lado bom de você,
o que me faz realmente ter

00:36:33:12 - 00:36:36:12
esse, tipo, adorno profundo para você.

00:36:37:06 - 00:36:39:13
E eu quero ser seu.

00:36:39:13 - 00:36:43:04
É como,
você sabe, é apenas um

00:36:43:12 - 00:36:47:03
um afeto e amor geral.

00:36:50:14 - 00:36:51:16
Para você porque

00:36:51:16 - 00:36:54:16
das coisas que eu vi que eu,
que eu,

00:36:55:12 - 00:36:58:23
Vou ser honesto com você agora,
estou passando por um momento muito difícil

00:36:59:08 - 00:37:02:22
escolhendo acreditar que essas partes boas
eram realmente reais.

00:37:03:17 - 00:37:06:17
É muito difícil
para mim me apegar a isso agora.

00:37:07:05 - 00:37:09:05
Como cada vez
que você me derruba, como se estivesse

00:37:09:05 - 00:37:12:05
só que está
cada vez mais fora de alcance.

00:37:12:09 - 00:37:17:06
E é isso que eu tenho no meu vídeo
sobre os problemas de saúde mental.

00:37:17:06 - 00:37:20:06
Eu te disse, tipo,
você tem que ter um, é um porquê importante.

00:37:21:13 - 00:37:24:13
Esse é o porquê.

00:37:26:09 - 00:37:29:09
É minha crença em você

00:37:30:01 - 00:37:32:23
e minha disposição
de passar pelo fogo do caralho,

00:37:32:23 - 00:37:36:21
de ter uma vida saudável

relacionamento e.

00:37:41:07 - 00:37:41:20
Eu disse isso,

00:37:41:20 - 00:37:45:20
mas honestamente,
a maneira como esse relacionamento foi,

00:37:47:03 - 00:37:50:03
como se não tivesse sido pior para mim.

00:37:51:10 - 00:37:54:05
Quer dizer, eu já era realmente
muito forte mentalmente.

00:37:54:05 - 00:37:57:05
Então, tipo, eu tenho um pouco, pelo menos

00:37:57:05 - 00:38:02:06
alguma direção decente sobre mim agora,
mas um pouco mais disso e

00:38:02:08 - 00:38:07:19
Eu praticamente não consigo ser pai
dos meus filhos, não consigo aparecer para trabalhar,

00:38:08:01 - 00:38:13:16
tipo, tenho hábitos muito ruins, tipo muito,
muito rápido.

00:38:14:01 - 00:38:18:15
Se eu continuar nesse espaço,
é onde eu acabaria 100%.

00:38:19:11 - 00:38:22:02
E é por isso que eu tenho que ser capaz
de impor os limites,

00:38:22:02 - 00:38:25:02
porque quando eu entro nesse estado, tipo,

00:38:25:06 - 00:38:28:06
sabe, eu não posso ser pai,

00:38:29:04 - 00:38:32:08
assumir muito, cuidar de mim,
muito menos, muito menos de outra pessoa.

00:38:33:08 - 00:38:36:08
Então é assim que eu me sinto.

00:38:36:14 - 00:38:40:22
É por isso que sinto que esse
relacionamento vai fazer comigo

00:38:41:08 - 00:38:44:13
se essas coisas que estão acontecendo
continuarem acontecendo.

00:38:46:14 - 00:38:47:11
E meu

00:38:47:11 - 00:38:53:00
objetivo é, é que eu me dê graça
pelo que eu dou a eles por nós

00:38:53:00 - 00:38:56:01
e o que eu permiti que acontecesse
e o que eu também,

00:38:56:15 - 00:39:00:09
por causa da minha participação,
também possibilitei e apoiei isso.

00:39:01:07 - 00:39:04:07
Sinceramente,

00:39:05:14 - 00:39:08:14
Por causa disso.

00:39:09:06 - 00:39:11:08
Nenhuma ligação.

00:39:11:08 - 00:39:15:08
Desculpe.

00:39:16:11 - 00:39:18:12
Disse tudo o que você permite.

00:39:18:12 - 00:39:20:13
E você apoiou.

00:39:20:13 - 00:39:20:19
Sim.

00:39:20:19 - 00:39:21:17
Quer dizer, basicamente eu não

00:39:21:17 - 00:39:24:22
porque eu sou legal, mas, tipo,
eles ainda querem porque eu ainda queria.

00:39:24:22 - 00:39:27:22
Tipo,
não tem, não é como se não fosse tanto

00:39:29:04 - 00:39:32:00
tipo, honestamente, tipo eu estava literalmente
no lugar onde eu estava tipo,

00:39:32:00 - 00:39:35:20
você está saindo a cada dois dias
tipo duas vezes por dia

00:39:37:01 - 00:39:40:01
e tipo.

00:39:41:09 - 00:39:41:18
Sabe,

00:39:41:18 - 00:39:45:17
minha única coisa que eu poderia ter
nesse momento porque você não se importava

00:39:45:17 - 00:39:49:06
sobre qualquer outra coisa, era apenas para ser como,
ok, você pode se mudar.

00:39:49:06 - 00:39:51:13
Tipo,
essa é a escolha que eu tive que fazer.

00:39:51:13 - 00:39:55:07
Tipo, era ou era como,
você vive com isso ou tipo você se muda,

00:39:56:15 - 00:39:59:15
tipo imediatamente e.

00:40:01:10 - 00:40:02:16
Com isso,

00:40:02:16 - 00:40:05:16
especialmente com onde eu estava
e o que eu estava começando

00:40:06:10 - 00:40:09:10
e o que eu passei
para me recuperar,

00:40:10:12 - 00:40:13:17
Eu literalmente passei por isso,
tipo tudo isso

00:40:14:08 - 00:40:17:08
com você.

00:40:18:06 - 00:40:20:13
Tipo eu passei por tudo isso com você.

00:40:20:13 - 00:40:22:19
Eu literalmente encontrei um novo emprego.

00:40:22:19 - 00:40:26:23
Saí do desemprego
uma semana depois que nos encontramos novamente.

00:40:29:04 - 00:40:31:21
E então comecei meu novo emprego
na semana seguinte.

00:40:31:21 - 00:40:33:03
Eu estava literalmente desanimado.

00:40:33:03 - 00:40:36:11
Eu estava no Mambo Karibu
com US$ 30 no meu bolso.

00:40:37:04 - 00:40:39:23
Era isso.

00:40:39:23 - 00:40:42:23
Eu estava apenas saindo
para ter algum tipo de,

00:40:43:03 - 00:40:45:23
você sabe, felicidade
porque eu estava basicamente em casa,

00:40:45:23 - 00:40:49:09
desenhar coisas
e então tudo começou a estourar.

00:40:49:09 - 00:40:52:01
Eu consegui o emprego
e tudo o mais por qualquer coisa.

00:40:52:01 - 00:40:56:17
Mas eu literalmente lutei para voltar
daquele estado que estou lhe contando.

00:40:57:16 - 00:41:00:09
Eu lutei contra esse estado

00:41:00:09 - 00:41:05:19
de puro medo e pânico, como nas minhas
entrevistas e coisas diferentes assim.

00:41:05:19 - 00:41:09:00
Eu lutei contra isso
para agora ter uma empresa

00:41:09:00 - 00:41:12:05
que gera no mínimo US$ 40.000
por mês de receita.

00:41:14:13 - 00:41:17:13
Como se eu tivesse feito essa merda em um ano e meio.

00:41:20:15 - 00:41:23:02
Tipo.

00:41:23:02 - 00:41:23:07
É.

00:41:23:07 - 00:41:26:11
Mas eu não posso, eu não posso ir,

00:41:28:13 - 00:41:31:22
Não é bem assim. Sim.

00:41:31:22 - 00:41:35:07
E também com seu apoio,

00:41:35:16 - 00:41:38:16
você definitivamente me ajuda

00:41:38:16 - 00:41:41:16
100%.

00:41:42:10 - 00:41:43:02
100%.

00:41:43:02 - 00:41:45:15
E você sacrificou muito
quando eu estava trabalhando.

00:41:45:15 - 00:41:48:15
Quer dizer,
Eu sinto que estava sacrificando muito também,

00:41:48:23 - 00:41:51:17
Mas além disso,
você estava sacrificando muito.

00:41:51:17 - 00:41:54:21
Sim, eu também fiz isso. Então,

00:41:56:08 - 00:41:59:02
Sim, eu acho que, sabe,

00:41:59:02 - 00:42:02:14
quando você diz coisas que você era,
você era antes, cara, que você.

00:42:03:21 - 00:42:06:06
Eu sinto

00:42:06:06 - 00:42:09:02
é como em qualquer lugar

00:42:09:02 - 00:42:11:19
também não é não é como se

00:42:11:19 - 00:42:14:19
não teria acontecido
se você não estivesse lá.

00:42:14:22 - 00:42:16:00
Certo. Mas foi.

00:42:16:00 - 00:42:19:00
Mas eu vou
mas eu vou dizer que eu quero dizer isso.

00:42:19:02 - 00:42:22:14
Mas eu direi, mas eu direi que
definitivamente

00:42:23:00 - 00:42:26:00
foi útil,

00:42:26:12 - 00:42:30:04
foi muito amoroso
e eu realmente, realmente apreciei.

00:42:30:06 - 00:42:33:21
E é provavelmente isso
isso em si que

00:42:35:11 - 00:42:38:11
e como eu me senti quando isso estava acontecendo

00:42:38:16 - 00:42:41:16
é provavelmente a única razão pela qual estou aqui.

00:42:41:17 - 00:42:45:06
Na verdade, para ser honesto com você,
eu queria isso

00:42:45:12 - 00:42:48:12
tanto.

00:42:54:12 - 00:42:55:11
E é a primeira vez

00:42:55:11 - 00:42:59:00
que eu realmente me senti
em um relacionamento.

00:43:00:12 - 00:43:07:11
De uma forma que eu realmente apreciei.

00:43:07:11 - 00:43:10:11
E eu realmente amo.

00:43:10:14 - 00:43:13:09
E é, novamente, provavelmente
a única razão pela qual estou aqui agora.

00:43:18:04 - 00:43:19:15
É minha

00:43:19:15 - 00:43:23:07
apenas fé cega e completa

00:43:23:14 - 00:43:26:14
que que que que que

00:43:26:15 - 00:43:29:15
parte de você ou quem você era
naqueles momentos

00:43:31:11 - 00:43:34:11
é realmente quem você é.

00:43:42:01 - 00:43:45:11
Como se fosse quem você é,
então você o incorpora.

00:43:46:00 - 00:43:49:14
Não é uma escolha ser ou não ser.

00:43:50:03 - 00:43:52:21
Você é isso ou não é.

00:43:52:21 - 00:43:55:21
É isso que você é,
e essa é sua identidade.

00:43:57:11 - 00:44:00:11
E esse é realmente seu propósito.

00:44:03:15 - 00:44:06:15
Ser inteiro e você.

00:44:12:18 - 00:44:15:11
Tipo, essa é a porra da coisa

00:44:15:11 - 00:44:18:11
bem ali.

00:44:18:23 - 00:44:22:04
Então se você não é uma coisa,

00:44:23:05 - 00:44:23:16
você é?

00:44:23:16 - 00:44:26:20
Você provavelmente não é.

00:44:27:09 - 00:44:29:16
Ok. Então se você não é você, então o que?

00:44:29:16 - 00:44:31:10
Se você não é você de verdade.

00:44:31:10 - 00:44:33:15
Então o que você é?

00:44:33:15 - 00:44:36:03
Você é

00:44:36:03 - 00:44:39:20
personalidades programadas
para lidar com certas circunstâncias,

00:44:41:06 - 00:44:44:06
certo. Ou

00:44:44:11 - 00:44:47:18
você está apenas tentando gerenciar tudo
ao seu redor para se sentir seguro.

00:44:49:14 - 00:44:51:02
Deus, eu deveria gravar isso, porra.

00:44:51:02 - 00:44:54:01
Isso é brilhante.

00:45:00:06 - 00:45:03:06
Ou você é ou não é.

00:45:04:02 - 00:45:06:03
Seu amor não é uma escolha.

00:45:06:03 - 00:45:06:14
Ou não.

00:45:06:14 - 00:45:08:16
O amor não é apenas um sentimento, certo?

00:45:08:16 - 00:45:10:02
É sua escolha real.

00:45:10:02 - 00:45:11:05
É, é, é verdade.

00:45:11:05 - 00:45:14:09
Amor é fazer algo que

00:45:16:08 - 00:45:18:20
você deveria fazer

00:45:18:20 - 00:45:23:02
apesar de talvez não querer fazer,
ou estar relutante

00:45:23:02 - 00:45:28:03
em fazer, ou estar cansado para fazer,
ou estar muito machucado para fazer.

00:45:29:00 - 00:45:31:21
Tipo, se isso não for

00:45:31:21 - 00:45:33:13
de um, de um, você sabe,

00:45:33:13 - 00:45:36:13
nós dizemos tipo,
Eu não quero, não quero me perder.

00:45:36:21 - 00:45:39:21
Eu não quero me perder no sentido de que,

00:45:40:02 - 00:45:43:02
você sabe.

00:45:43:04 - 00:45:46:04
Quando alguém tipo,

00:45:46:07 - 00:45:47:06
merda, do que eu estava falando?

00:45:47:06 - 00:45:51:16
Só para o corpo
quando você está se perdendo.

00:45:51:20 - 00:45:54:08
Sim, sim. Então, tipo, você sabe.

00:45:54:08 - 00:45:55:08
Sim. Então, tipo.

00:45:58:03 - 00:45:59:07
Essa é a única coisa que você tem.

00:45:59:07 - 00:46:02:07
Ou você é pré-programado

00:46:03:03 - 00:46:08:06
personalidades não conscientes
reagindo a estímulos diferentes

00:46:08:06 - 00:46:12:04
e você apenas flutua
entre personalidades diferentes ou

00:46:14:02 - 00:46:16:07
você é uma personalidade,

00:46:16:07 - 00:46:19:17
mas você acha que seu ego é tão grande
que você acha

00:46:19:17 - 00:46:23:00
que você pode controlar a porra,
você sabe, o espaço

00:46:23:00 - 00:46:26:02
continuum temporal para que sua vida
siga do jeito que você quer.

00:46:26:18 - 00:46:28:11
E isso não é verdade.

00:46:28:11 - 00:46:33:01
E então essa é uma vida muito decepcionante,
frustrante e agressiva.

00:46:33:10 - 00:46:37:05
E a outra coisa é,
é que você olha para você e para quem você é,

00:46:38:01 - 00:46:42:00
e se você soubesse que você e você soubesse
que você está seguro, você ficaria frenético?

00:46:42:21 - 00:46:45:21
Você seria rápido em julgar?

00:46:46:13 - 00:46:49:13
Você seria, você sabe,

00:46:49:18 - 00:46:52:18
não ouvir as pessoas, não se importar
com o que elas dizem?

00:46:52:21 - 00:46:54:07
Não, você não
não faça nenhuma dessas coisas.

00:46:54:07 - 00:46:58:08
Você não poderia ser nenhuma dessas coisas, porque se você fosse você, não importaria.

00:46:59:20 - 00:47:00:18
Porque a pessoa que faz

00:47:00:18 - 00:47:03:19
essas outras coisas e tem esse
tipo de coração não faz essas outras merdas.

00:47:03:21 - 00:47:06:21
Há outras coisas.

00:47:14:11 - 00:47:15:10
É uma escolha.

00:47:15:10 - 00:47:16:21
É uma escolha do caralho.

00:47:16:21 - 00:47:18:12
E eu sei que já disse isso um milhão de vezes.

00:47:18:12 - 00:47:18:18
Você vai.

00:47:18:18 - 00:47:21:21
Onde você vai, há uma escolha absoluta.

00:47:23:08 - 00:47:27:11
E eu acho que é realmente uma pergunta muito
difícil para alguém responder.

00:47:27:22 - 00:47:30:13
Mas se eles realmente puderem

00:47:30:13 - 00:47:34:15
tipo se eu te perguntasse, eu posso te dizer
sem rodeios o que eu amo em você

00:47:35:14 - 00:47:38:14
apesar de tudo que aconteceu, eu,

00:47:39:10 - 00:47:41:06
Eu não sei se já ouvi

00:47:41:06 - 00:47:44:06
nada assim de você,

00:47:45:05 - 00:47:48:05
na verdade.

00:47:51:00 - 00:47:51:19
E eu tenho, por

00:47:51:19 - 00:47:55:02
ninguém nunca ouviu por que eu te amei.

00:47:56:10 - 00:47:58:18
Sim,

00:47:58:18 - 00:48:02:00
Eu não, não estou dizendo e nunca
Eu não estou dizendo que nunca aconteceu,

00:48:02:14 - 00:48:05:17
mas eu realmente honestamente, se eu olhar,

00:48:05:22 - 00:48:10:07
se eu olhar dentro da minha própria cabeça
e eu pensar sobre

00:48:10:22 - 00:48:13:13
o que eu acho que ela pensa sobre mim.

00:48:17:18 - 00:48:20:16
Ou por que ela me ama?

00:48:20:16 - 00:48:23:16
Eu estou. Eu estou em branco.

00:48:36:00 - 00:48:36:14
Eu estou internado.

00:48:36:14 - 00:48:39:10
Essas pessoas. Olha, eu não estou.
Vou embora alguns minutos depois.

00:48:39:10 - 00:48:41:02
Essas palavras e conversa especial.

00:48:41:02 - 00:48:43:09
Então eu estou apenas pulando em você.

00:48:43:09 - 00:48:45:11
Mas é 7 ou 7.

00:48:45:11 - 00:48:48:07
Deixa eu só.

00:48:48:07 - 00:48:49:21
É.

00:48:49:21 - 00:48:52:21
Restaurante.

00:48:55:11 - 00:48:58:11
Eu estava certo.

00:49:03:06 - 00:49:06:06
Sim. Ok, eu tenho que ir

00:49:06:21 - 00:49:07:07
4 ou 5.

00:49:07:07 - 00:49:07:20
Não tenho certeza.

00:49:07:20 - 00:49:10:07
Max, eu tenho que ir em alguns minutos.

00:49:10:07 - 00:49:13:07
De qualquer forma,

00:49:14:02 - 00:49:16:17
É uma pergunta difícil de fazer,
mas se você olhar para alguém,

00:49:16:17 - 00:49:20:10
você diz que isso é, você sabe,
você sabe quem você é,

00:49:20:12 - 00:49:25:04
e você é essa pessoa,
o que significa que essa pessoa faz isso.

00:49:25:18 - 00:49:28:23
Essa pessoa não faz essa coisa
e essa outra porra de coisa.

00:49:28:23 - 00:49:31:23
De jeito nenhum. Você está certo.

00:49:32:10 - 00:49:36:07
Então, se você é você e você é uma pessoa

00:49:36:21 - 00:49:40:20
e você não está controlando o
ambiente, você está em paz

00:49:41:23 - 00:49:42:07
e você

00:49:42:07 - 00:49:45:07
se sente seguro
porque você tem fé na segurança

00:49:46:09 - 00:49:47:23
equipe e você trata as pessoas

00:49:47:23 - 00:49:51:09
com gentileza,
e você não leva as coisas para o lado pessoal

00:49:51:19 - 00:49:55:01
por causa do fato de que você geralmente não está
tentando se proteger

00:49:55:01 - 00:49:58:00
do mundo e tudo
e todos os goblins

00:49:58:00 - 00:50:01:00
e demônios.

00:50:02:20 - 00:50:05:03
É uma porra, é uma, é uma, é como.

00:50:05:03 - 00:50:08:03
É como se fosse um roteiro.

00:50:08:19 - 00:50:11:02
E você lê uma linha biográfica,

00:50:11:02 - 00:50:14:02
você sabe, ou algo assim sobre,
como um personagem

00:50:15:04 - 00:50:17:11
e uma cena

00:50:17:11 - 00:50:20:16
e você decide quem é a personificação

00:50:20:16 - 00:50:23:16
daquela pessoa,
e então você simplesmente faz,

00:50:25:03 - 00:50:28:03
e então parece muito, muito bom.

00:50:28:21 - 00:50:31:21
Porque quem não quer ser isso?

00:50:43:14 - 00:50:46:04
De qualquer forma, você sabe,

00:50:46:04 - 00:50:49:04
meu meu meu meu minguando

00:50:49:11 - 00:50:53:08
a fé realmente precisa de um reforço
agora mesmo.

00:50:54:06 - 00:50:58:05
E eu não consigo nem te dizer como

00:50:59:17 - 00:51:02:17
o cálculo da situação de Sarah,

00:51:03:14 - 00:51:06:04
você sabe, agrava a dificuldade

00:51:06:04 - 00:51:09:18
nisso mais emocionalmente
e tudo mais.

00:51:11:15 - 00:51:14:15
Então são.

00:51:17:16 - 00:51:20:16
Você tem.

00:51:21:17 - 00:51:22:18
Talvez ela não tenha feito isso.

00:51:22:18 - 00:51:23:16
Ela não fez nada.

00:51:23:16 - 00:51:26:11
Você se importa

00:51:26:11 - 00:51:28:02
virar.

00:51:28:02 - 00:51:31:02
Ah, sério, por favor.

00:51:32:22 - 00:51:34:17
Eu estava falando sobre mim agora.

00:51:34:17 - 00:51:37:10
Ok. Sério, foi você.

00:51:37:10 - 00:51:41:01
Você você era como eu disse, ela estava sofrendo.

00:51:41:11 - 00:51:43:00
Ela estava sofrendo muito.

00:51:43:00 - 00:51:45:07
Isso não significa que você vá e destrua
pessoas assim.

00:51:45:07 - 00:51:46:23
Ele está sofrendo muito ad.

00:51:46:23 - 00:51:49:05
Ela é bonita. Muito má.
E eu estava te machucando.

00:51:49:05 - 00:51:52:13
E você estava me machucando com ela
por algum tempo,

00:51:53:00 - 00:51:55:06
então isso não significa nada, certo?

00:51:55:06 - 00:51:57:14
É disso que estou falando.
Não significa que você não se machuque.

00:51:57:14 - 00:51:59:15
Não significa que você está machucado,
isso importa

00:51:59:15 - 00:52:02:20
só porque algo
que você fez me machucou ou machucou,

00:52:04:04 - 00:52:05:05
não significa que você está machucado.

00:52:05:05 - 00:52:07:17
Isso importa? Ambas as coisas são verdadeiras.

00:52:07:17 - 00:52:09:21
Não tem como.

00:52:09:21 - 00:52:11:03
Não, não tem como vencer.

00:52:11:03 - 00:52:14:03
E eu quero dizer, não é sobre vencer
verbalmente,

00:52:14:03 - 00:52:16:04
realmente se desculpando, estando lá.

00:52:16:04 - 00:52:18:07
E ele também não fez isso.

00:52:18:07 - 00:52:20:11
E ela não estava lá
e ela passou dos limites.

00:52:20:11 - 00:52:23:11
E você também sabe que ela não

00:52:24:12 - 00:52:26:21
Eu não concordo com isso. Levantou-se.

00:52:26:21 - 00:52:29:05
Sim, tenho que entrar agora.

00:52:29:05 - 00:52:32:01
Desculpe-me por deixar assim,
mas eu vou consertar você mais tarde. Sim.

00:52:32:01 - 00:52:32:16
Obrigado.

00:52:32:16 - 00:52:38:11
Ok, ok, eu vou verificar e eu vou verificar você
mais tarde, depois que eu sair do meu jantar.

00:52:38:16 - 00:52:40:19
Ok. Desculpe-me por sair abruptamente.

00:52:40:19 - 00:52:42:10
Eu não estou tentando ser.

00:52:42:10 - 00:52:45:10
Desculpe se isso faz você aparecer.

00:52:46:00 - 00:52:47:11
Desculpe.

00:52:47:11 - 00:52:50:11
Obrigado.

00:52:53:15 - 00:52:54:08
Desculpe por não ter

00:52:54:08 - 00:52:57:21
Eu provavelmente pareço
como se estivesse saindo abruptamente

00:52:59:06 - 00:53:01:18
e talvez tentando te machucar,

00:53:01:18 - 00:53:04:18
você sabe, indo a esse jantar
ou qualquer outra coisa.

00:53:04:18 - 00:53:06:23
Ok? Não é uma coisa de namoro.

00:53:06:23 - 00:53:08:13
Eu prometo a você.

00:53:08:13 - 00:53:11:09
Está literalmente neste slogan
que isto não é para encontros.

00:53:11:09 - 00:53:11:18
Ok?

00:53:11:18 - 00:53:17:15
E, e eu só estava indo
porque estou realmente preocupado com o tempo

00:53:17:15 - 00:53:20:15
porque não quero me atrasar
e já estou atrasado.

00:53:20:15 - 00:53:23:08
Então eu fiquei
porque eu queria falar com você.

00:53:23:08 - 00:53:26:07
Ok. Mas,

00:53:26:07 - 00:53:27:03
você estava falando.

00:53:27:03 - 00:53:28:21
Ok?

00:53:28:21 - 00:53:29:12
Ok.

00:53:29:12 - 00:53:31:18
Obrigado por falar comigo.

00:53:31:18 - 00:53:32:18
De nada.
"""

srt_content = convert_to_srt(translated_text)

# Write the SRT content to a file
output_file = 'output.srt'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(srt_content)

print(f"SRT file has been created: {output_file}")