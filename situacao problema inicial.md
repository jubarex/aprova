Cara estamos estruturando uma ideia diferente porque o gargalo na verdade é em outro lugar, me ajude a fazer um plano de projeto/escopo baseado no seguinte:

Quero agora fazer algo como um "age of empires" para gerenciar os pipelines de pergunta com as prefeituras e processo

O que acontece é que uma prefeitura contrata a aprova
a aprova já tem formulários template baseando-se em processos e legislações, e na implantação ela mostra os templates pra prefeitura e pros responsáveis pelo processo da prefeitura, e vai tendo que perguntar pros responsáveis que alterações são necessárias como alterações de nome e campos a mais no formulário ou outros documentos que precisam ser anexados. O que acontece é que muitas vezes a propria prefeitura não conhece o processo/legislação e manda só um documento ou pede meio que uma consultoria da aprova pra ver como deveria ser o processo e o que recomenda colocar ou não, pois é municipal né essas diferenças. E aí o implantador da aprova tem que fazer reuniões (eles conseguem fazer 2 reuniões de 1h por semana por cliente onde discutem 3 processos mas o total são 70 processos por implantação então o que não dá pra discutir na reunião eles tem que fazer assíncronamente pelo whatsapp)

A ideia seria automatizar esse controle agêntico do whatsapp como se fosse um age of empires:

o meu soldado vai ter acesso a perguntas, conhecimento e processos, e os templates de formulário e vai criar uma lista de perguntas (vamos chamar de jornada) pra fazer para o responsável do processo pra validar o formulário.

Então a gente levanta os responsáveis da prefeitura - que tem responsáveis centrais e responsáveis específicos e então a gente tem também que levantar lacunas de responsável

Com a lista de responsáveis a gente organiza ela meio que em hierarquia e também organiza a lista de perguntas(jornada) de cada responsável

Então o agente começa o loop e manda mensagem no whatsapp pra aquele número

Começa o loop né
Manda a pergunta
Recebe de resposta ou um audio ou texto ou documento ou foto
Precisa então analisar a jornada que foi criada e propor: novas perguntas caso necessário, mudanças necessárias na jornada ou no formulário, ou também pedir apoio do implantador pra essa parte(intervenção humana)
e ele vai repetir esse processo até o fim da jornada daquele cliente, então ele meio que tem que ir conversando com a prefeitura pra ir ajustando a jornada (perguntas) pra poder ajustar o formulário e o objeto disso é o formulário completamente validado e aprovação da prefeitura e do implantador para aquele processo

Vamos fazer então um soldado desses para cada um dos processos. Eu quero ter meus sodlados e saber em que estado ele está e quero saber onde intervir e quando caso ele precise (tipo age of empires)
Eles marcham(rodam sozinhos o loop até precisar de intervenção) Lembra warcraft até

Claro, eu vou ter várias cidades(prefeituras) e consigo ver em que etapas estão os meus soldados pra cada uma das prefeituras uma visualização meio de mapa né medieval

A ideia é que o uso do whatsapp não seja pela api oficial, e seja algo mais lento mas automático! mesmo que precise usar um computador pra isso, e até temos disponibilidade de conseguir mais numeros de whatsapp.

Claro pontos importantes: levantar a lista de repsonsáveis e também saber perguntar pros responsáveis se tem o contato de outro responsável pra gente entrar em contato e fazer uma pergunta. Isso pode acontecer também! Existem perguntas de uma jornada que podem ser para um responsável mas no meio precisar entrar em contato com outro e precisamos garantir que o fluxo siga até o fim.
