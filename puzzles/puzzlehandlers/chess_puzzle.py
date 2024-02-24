import traceback
import json
from django.views.decorators.http import require_POST

@require_POST
def submit(request):

    try:
        body = json.loads(request.body)

        if not (1 <= len(body['answer']) < 50):
            return {
                'error': 'Please enter a reasonable answer.',
                'correct': False,
            }

        rot13 = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ','NOPQRSTUVWXYZABCDEFGHIJKLM')
        encoded = body['answer'].upper().translate(rot13)

        stages = dict()
        

        stages['GUVF CHMMYR VF ZBFGYL ABG NOBHG ONFRONYY'] = """
        <p>Congratulations! You are now ready to face five challengers, on five (randomly ordered) boards below, in five different games. 
Each of those games is different - there are games of Combination Chess, Progress Chess, Replacement Chess, Standard Chess, and Travel Chess.  
Here are your opponent's moves in the first game:</p>
<div style="padding-left:45%"><ol>
<li>?-2B</li>
<li>?-LF</li>
<li>?-C</li>
<li>?-LF</li>
<li>?-SS</li>
<li>?-P</li>
<li>?-CF</li>
<li>?-LF</li>
</ol></div>
        <p> This puzzle is mostly not about Baseball ... or ...</p>
        """

        stages['PBYBENQB'] = """
        <p>Congratulations! You are now ready to face five challengers, on five (randomly ordered) boards below, in five different games. 
Each of those games is different - there are games of Combination Chess, Progress Chess, Replacement Chess, Standard Chess, and Travel Chess.  
Here are your opponent's moves in the second game:</p>
<div style="padding-left:45%"><ol>
<li>?-GJT</li>
<li>?-COS</li>
<li>?-TAD</li>
<li>?-HDN</li>
<li>?-LAA</li>
<li>?-DEN</li>
<li>?-DRO</li>
<li>?-GJT</li>
<li>?-COS</li>
</ol></div>
        <p> This puzzle is mostly not about Baseball or Colorado ... or ...</p>
        """

        stages['GUVF ZBAGU'] = """
        <p>Congratulations! You are now ready to face five challengers, on five (randomly ordered) boards below, in five different games. 
Each of those games is different - there are games of Combination Chess, Progress Chess, Replacement Chess, Standard Chess, and Travel Chess.  
Here are your opponent's moves in the third game:</p>
<div style="padding-left:45%"><ol>
<li>?-13</li>
<li>?-27</li>
<li>?-9</li>
<li>?-9</li>
<li>?-7</li>
<li>?-18</li>
<li>?-22</li>
<li>?-22</li>
<li>?-24</li>
</ol></div>
        <p> This puzzle is mostly not about Baseball or Colorado or This Month ... or ...</p>
        """
 

        stages['CNFFVAT TB'] = """
        <p>Congratulations! You are now ready to face five challengers, on five (randomly ordered) boards below, in five different games. 
Each of those games is different - there are games of Combination Chess, Progress Chess, Replacement Chess, Standard Chess, and Travel Chess.  
Here are your opponent's moves in the fourth game:</p>
<div style="padding-left:45%"><ol>
<li>?-Atl</li>
<li>?-Ver</li>
<li>?-Atl</li>
<li>?-Ten</li>
<li>?-Ind</li>
<li>?-Med</li>
<li>?-Vir</li>
<li>?-Pac</li>
</ol></div>
        <p> This puzzle is mostly not about Baseball or Colorado or This Month or Passing Go ... or ...</p>
        """

        stages['RYRZRAGF'] = """
        <p>Congratulations! You are now ready to face five challengers, on five (randomly ordered) boards below, in five different games. 
Each of those games is different - there are games of Combination Chess, Progress Chess, Replacement Chess, Standard Chess, and Travel Chess.  
Here are your opponent's moves in the fifth game:</p>
<div style="padding-left:45%"><ol>
<li>?-27</li>
<li>?-29</li>
<li>?-24</li>
<li>?-34</li>
<li>?-24</li>
<li>?-79</li>
<li>?-1</li>
<li>?-42</li>
<li>?-9</li>
<li>?-3</li>
<li>?-24</li>
<li>?-73</li>
</ol></div>
        <p> This puzzle is mostly not about Baseball or Colorado or This Month or Passing Go or Elements. </p>
        """

       
        stages['OVFUBC'] = """
        <p>All done! Call that in using the official answer checker.</p>
        """
        
        if encoded in stages:
            return {'correct': True, 'content': stages[encoded]}
        
        return {'correct': False}
    except:
        traceback.print_exc()
        return {'error': 'An error occurred!', 'correct': False}
